from __future__ import annotations

import time
from typing import List, Optional
from urllib.parse import quote

import httpx

from app.schemas.domain import TransportOption


class TrainProvider:
    STATION_CODES = {
        "北京": "BJP", "北京南": "VNP", "北京西": "BXP", "北京北": "VAP", "北京丰台": "FTP",
        "南京": "NJH", "南京南": "NKH", "南京东": "NFH",
        "上海": "SHH", "上海虹桥": "AOH", "上海南": "SNH", "上海西": "SXH",
        "西安": "XAY", "西安北": "EAY",
        "杭州": "HZH", "杭州东": "HGH",
        "苏州": "SZH", "苏州北": "OHH",
        "广州": "GZQ", "广州南": "IZQ",
        "深圳": "SZQ", "深圳北": "IOQ",
    }

    SEAT_CLASS_MAP = {
        "9": "商务座",
        "P": "特等座",
        "M": "一等座",
        "O": "二等座",
        "W": "无座",
        "D": "优选一等座",
        "F": "动卧",
        "I": "高级软卧",
        "J": "软卧",
        "4": "软卧",
        "3": "硬卧",
        "1": "硬座",
    }

    def __init__(self, timeout: float = 35.0):
        self.timeout = timeout

    async def search_single_train(self, from_city: str, to_city: str, travel_date: Optional[str] = None) -> dict:
        from app.services.train_cache import get_cached, set_cached

        date = travel_date or ""
        cached = get_cached(from_city, to_city, date)
        if cached:
            return cached

        raw = await self._search_tongcheng_api(from_city, to_city, date)
        parsed = self._parse_results(raw.get("trains", []), from_city, to_city, date)
        result = {
            "query": {
                "from_city": from_city,
                "to_city": to_city,
                "travel_date": date,
            },
            "raw": raw,
            "parsed": parsed,
            "count": len(parsed),
            "notices": raw.get("notices", []),
            "booking_url": self.build_booking_url(from_city, to_city, date),
        }
        if parsed:
            set_cached(from_city, to_city, date, result)
        return result

    def load_transport_options(self, from_city: str, to_city: str, travel_date: Optional[str] = None) -> List[TransportOption]:
        import asyncio

        raw = asyncio.run(self._search_tongcheng_api(from_city, to_city, travel_date or ""))
        parsed = self._parse_transport_options(raw.get("trains", []), from_city, to_city)
        parsed.sort(key=lambda x: (x.price, x.duration_min))
        return parsed[:12]

    def build_booking_url(self, from_city: str, to_city: str, travel_date: str) -> str:
        dep = self.STATION_CODES.get(from_city, "")
        arr = self.STATION_CODES.get(to_city, "")
        return (
            "https://www.ly.com/mergetrain/book1"
            f"?depStation={quote(dep)}&arrStation={quote(arr)}&depDate={quote(travel_date)}"
            f"&depStationName={quote(from_city)}&arrStationName={quote(to_city)}&type=ADULT"
        )

    async def _search_tongcheng_api(self, from_city: str, to_city: str, travel_date: str) -> dict:
        dep = self.STATION_CODES.get(from_city)
        arr = self.STATION_CODES.get(to_city)
        if not dep or not arr or not travel_date:
            return {
                "error": "missing_station_code",
                "trains": [],
                "notices": ["同程车站编码缺失或日期为空。"],
            }

        payload = {
            "depStation": dep,
            "arrStation": arr,
            "depDate": travel_date,
            "type": "ADULT",
            "traceId": str(int(time.time() * 1000)),
            "pid": 1,
            "ts": int(time.time() * 1000),
        }
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.ly.com",
            "referer": self.build_booking_url(from_city, to_city, travel_date),
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
                resp = await client.post("https://www.ly.com/trainsearchbffapi/trainSearch", json=payload)
                data = resp.json()
        except Exception as e:
            return {
                "error": str(e),
                "trains": [],
                "notices": [f"同程铁路查询异常: {e}"],
            }

        if not data.get("success"):
            return {
                "error": data.get("errorCode") or "request_failed",
                "message": data.get("errorMessage", ""),
                "trains": [],
                "notices": [f"同程铁路查询失败: {data.get('errorMessage') or data.get('errorCode')}"]
            }

        result = data.get("data") or {}
        return {
            "success": True,
            "traceId": data.get("traceId") or result.get("traceId"),
            "depStation": result.get("depStation", dep),
            "arrStation": result.get("arrStation", arr),
            "depDate": result.get("depDate", travel_date),
            "trains": result.get("trains") or [],
            "notices": [],
        }

    def _parse_results(self, items: list, from_city: str, to_city: str, travel_date: Optional[str]) -> List[dict]:
        parsed = []
        booking_url = self.build_booking_url(from_city, to_city, travel_date or "")
        for item in items:
            train_code = str(item.get("trainCode", "") or "")
            train_type = str(item.get("type", "") or "")
            train_avs = item.get("trainAvs") or []
            if not train_code:
                continue

            seat_items = []
            min_price = None
            for seat in train_avs:
                seat_info = self._parse_seat(seat)
                if not seat_info:
                    continue
                seat_items.append(seat_info)
                if min_price is None or seat_info["price"] < min_price:
                    min_price = seat_info["price"]

            parsed.append({
                "from_city": from_city,
                "to_city": to_city,
                "mode": "train",
                "train_no": train_code,
                "train_type": self._normalize_train_type(train_type, item.get("gdc")),
                "from_station": item.get("depStationName", from_city),
                "to_station": item.get("arrStationName", to_city),
                "depart_time": item.get("depTime", ""),
                "arrive_time": item.get("arrTime", ""),
                "depart_date": item.get("depDate", travel_date or ""),
                "arrive_date": item.get("arrDate", travel_date or ""),
                "arrival_day": item.get("arrivalDays", 0),
                "duration_text": item.get("runTime", ""),
                "duration_min": int(item.get("runTimeMin", 0) or 0),
                "start_station": item.get("startStationName", ""),
                "end_station": item.get("endStationName", ""),
                "price": float(min_price) if min_price is not None else None,
                "seat_summary": seat_items,
                "booking_url": booking_url,
                "sale_status": {
                    "can_buy_now": (item.get("limiter") or {}).get("canByNow"),
                    "sale_state": (item.get("limiter") or {}).get("saleState"),
                    "message": (item.get("limiter") or {}).get("message", ""),
                    "note": (item.get("limiter") or {}).get("note", ""),
                },
                "feature_tags": self._feature_tags(item),
            })

        parsed = [x for x in parsed if x.get("price") is not None]
        parsed.sort(key=lambda x: (x["price"], x["duration_min"], x["train_no"]))
        return parsed[:80]

    def _parse_transport_options(self, items: list, from_city: str, to_city: str) -> List[TransportOption]:
        parsed = []
        for item in items:
            min_price = None
            for seat in item.get("trainAvs") or []:
                seat_price = seat.get("price")
                if isinstance(seat_price, (int, float)) and seat_price > 0:
                    if min_price is None or seat_price < min_price:
                        min_price = float(seat_price)
            duration_min = int(item.get("runTimeMin", 0) or 0)
            if min_price is None or duration_min <= 0:
                continue
            parsed.append(
                TransportOption(
                    from_city=from_city,
                    to_city=to_city,
                    mode="train",
                    price=min_price,
                    duration_min=duration_min,
                    comfort_score=self._comfort_score(str(item.get("trainCode", "")), str(item.get("type", ""))),
                    transfer_count=0,
                )
            )
        return parsed

    def classify_train(self, option: TransportOption) -> str:
        return "high_speed" if option.comfort_score >= 0.85 else "normal"

    def score_transport_option(self, option: TransportOption, pace: str = "balanced") -> float:
        duration_penalty = option.duration_min * 0.12
        price_penalty = option.price * (0.9 if pace == "budget" else 1.0)
        return price_penalty + duration_penalty

    def _parse_seat(self, seat: dict) -> Optional[dict]:
        price = seat.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            return None
        code = str(seat.get("seatClassCode", "") or "")
        return {
            "seat_code": code,
            "seat_name": self.SEAT_CLASS_MAP.get(code, code or "未知座席"),
            "price": float(price),
            "availability": seat.get("num", ""),
            "candidate": bool(seat.get("candidate")),
            "berth_selectable": bool(seat.get("berthSelectable")),
            "student_bookable": bool(seat.get("stuBookable")),
            "student_price": seat.get("stuPrice"),
        }

    def _feature_tags(self, item: dict) -> list[str]:
        tags = []
        feature = item.get("feature") or {}
        if item.get("gdc"):
            tags.append("高铁/动车")
        if feature.get("checkInByIdCard"):
            tags.append("身份证进站")
        if feature.get("containSelectableBerth"):
            tags.append("可选铺")
        if feature.get("payByPoint") == "Y":
            tags.append("积分支付")
        if (item.get("limiter") or {}).get("saleState") == "1":
            tags.append("暂停发售")
        return tags

    def _normalize_train_type(self, train_type: str, gdc: Optional[bool]) -> str:
        if train_type in {"GD", "D"} or gdc:
            return "high_speed"
        if train_type in {"Z", "KT", "PK"}:
            return "normal"
        return train_type.lower() if train_type else "train"

    def _comfort_score(self, train_code: str, train_type: str) -> float:
        if train_type in {"GD", "D"} or train_code.startswith(("G", "D")):
            return 0.88
        if train_type in {"Z", "KT"}:
            return 0.65
        return 0.58
