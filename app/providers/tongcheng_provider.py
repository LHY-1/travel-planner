"""Tongcheng Provider - API-only version for cloud deployment."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from app.config.settings import BASE_DIR
from app.providers.base import BaseTravelProvider
from app.schemas.domain import TransportOption, CityFeature


class TongchengProvider(BaseTravelProvider):
    """同程航班查询 - 仅 API 模式，无浏览器依赖。"""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.project_dir = Path(BASE_DIR)
        self.city_codes = {
            "西安": "SIA",
            "北京": "PEK",
            "上海": "SHA",
            "杭州": "HGH",
            "南京": "NKG",
            "苏州": "SZV",
            "广州": "CAN",
            "深圳": "SZX",
            "成都": "CTU",
            "重庆": "CKG",
            "武汉": "WUH",
            "长沙": "CSX",
            "青岛": "TAO",
        }
        # 从环境变量读取 token（可选）
        self.tcsectoken = os.getenv("TONGCHENG_TOKEN", "")
        self.user_id = os.getenv("TONGCHENG_USER_ID", "0")

    async def search_single_flight(self, from_city: str, to_city: str, travel_date: str) -> dict:
        """直接调用 httpx API。"""
        return await self._search_single_flight_api(from_city, to_city, travel_date)

    async def get_transport_matrix(
        self, cities: List[str], travel_date: Optional[str] = None
    ) -> Dict[Tuple[str, str], List[TransportOption]]:
        matrix: Dict[Tuple[str, str], List[TransportOption]] = {}
        if not travel_date:
            for a in cities:
                for b in cities:
                    if a != b:
                        matrix[(a, b)] = []
            return matrix

        max_pairs = int(os.getenv("TONGCHENG_MAX_PAIRS", "3"))
        preferred_pairs: List[Tuple[str, str]] = []
        if len(cities) >= 2:
            for idx in range(len(cities) - 1):
                a, b = cities[idx], cities[idx + 1]
                if a != b and (a, b) not in preferred_pairs:
                    preferred_pairs.append((a, b))
        for a in cities:
            for b in cities:
                if a == b:
                    continue
                if (a, b) not in preferred_pairs:
                    preferred_pairs.append((a, b))

        for idx, (a, b) in enumerate(preferred_pairs):
            if idx >= max_pairs:
                matrix[(a, b)] = []
                continue
            data = await self.search_single_flight(a, b, travel_date)
            matrix[(a, b)] = self._parsed_dicts_to_options(a, b, data.get("parsed", []))
        return matrix

    async def get_city_features(self, cities: List[str], days: int) -> Dict[str, CityFeature]:
        result: Dict[str, CityFeature] = {}
        for city in cities:
            # 简化：使用默认酒店成本
            result[city] = CityFeature(city=city, experience_score=70.0, hotel_cost=260.0, stay_hours=8)
        return result

    def build_booking_url(self, from_city: str, to_city: str, travel_date: str) -> str:
        from_code = self.city_codes.get(from_city)
        to_code = self.city_codes.get(to_city)
        if from_code and to_code and travel_date:
            return (
                f"https://www.ly.com/flights/itinerary/oneway/{from_code}-{to_code}"
                f"?date={travel_date}&from={quote(from_city)}&to={quote(to_city)}"
                f"&fromairport=&toairport=&p=&childticket=0,0"
            )
        return f"https://www.ly.com/flights/itinerary/oneway/?date={travel_date}&from={quote(from_city)}&to={quote(to_city)}"

    # ── httpx API 直查 ────────────────────────────────────────────────────────

    async def _search_single_flight_api(self, from_city: str, to_city: str, travel_date: str) -> dict:
        from_code = self.city_codes.get(from_city)
        to_code = self.city_codes.get(to_city)
        booking_url = self.build_booking_url(from_city, to_city, travel_date)
        if not from_code or not to_code:
            return {
                "query": {"from_city": from_city, "to_city": to_city, "travel_date": travel_date},
                "raw": {"error": "missing_city_code_mapping"},
                "parsed": [],
                "count": 0,
                "booking_url": booking_url,
            }

        payload = {
            "Departure": from_code,
            "Arrival": to_code,
            "GetType": "1",
            "QueryType": "1",
            "fromairport": "",
            "toairport": "",
            "DepartureDate": travel_date,
            "DepartureName": from_city,
            "ArrivalName": to_city,
            "IsBaby": 0,
            "paging": {"cid": str(uuid.uuid4()), "dataflag": "some"},
            "DepartureFilter": "",
            "ArrivalFilter": "",
            "flat": 1,
            "plat": 1,
            "isFromKylin": 1,
            "refid": "0",
        }
        headers = self._build_api_headers(from_city, to_city, travel_date)

        raw: dict = {}
        parsed: list = []
        try:
            async with httpx.AsyncClient(timeout=45, headers=headers, follow_redirects=True) as client:
                resp = await client.post("https://www.ly.com/flights/api/getflightlist", json=payload)
                resp.raise_for_status()
                raw = resp.json()
                parsed = self._parse_flight_list_response(raw, from_city, to_city, travel_date)
        except Exception as e:
            raw = {"error": "api_request_failed", "message": str(e)}

        return {
            "query": {"from_city": from_city, "to_city": to_city, "travel_date": travel_date},
            "debug": {"source": "tongcheng-api"},
            "raw": raw,
            "parsed": parsed,
            "count": len(parsed),
            "booking_url": booking_url,
        }

    def _build_api_headers(self, from_city: str, to_city: str, travel_date: str) -> dict:
        now_ms = str(int(time.time() * 1000))
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "referer": self.build_booking_url(from_city, to_city, travel_date),
            "tcplat": "1",
            "tcversion": "1.1.0",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
            ),
        }
        if self.tcsectoken:
            headers["tcsectoken"] = self.tcsectoken
            headers["tcsessionid"] = f"{self.user_id}-{now_ms}"
            headers["tctracerid"] = f"{self.user_id}-{now_ms}"
        return headers

    def _parse_flight_list_response(
        self, raw: dict, from_city: str, to_city: str, travel_date: str
    ) -> List[dict]:
        booking_url = self.build_booking_url(from_city, to_city, travel_date)
        body = raw.get("body", {}) if isinstance(raw, dict) else {}
        items = body.get("FlightInfoSimpleList", []) or []
        parsed = []
        for item in items:
            price = self._pick_price(item)
            duration_text = item.get("spantime", "")
            duration_min = self._parse_duration_text(duration_text)
            if price is None or duration_min <= 0:
                continue
            transfer_count = int(item.get("stopNum", 0) or 0)
            parsed.append({
                "from_city": from_city,
                "to_city": to_city,
                "mode": "flight",
                "price": float(price),
                "duration_min": duration_min,
                "comfort_score": 0.68 if transfer_count else 0.82,
                "transfer_count": transfer_count,
                "airline": item.get("airCompanyName", ""),
                "flight_no": item.get("flightNo", ""),
                "depart_time": item.get("flyOffOnlyTime", ""),
                "arrive_time": item.get("arrivalOnlyTime", ""),
                "depart_airport": item.get("originAirportShortName", ""),
                "arrive_airport": item.get("arriveAirportShortName", ""),
                "duration_text": duration_text,
                "meal": item.get("mfgd", "") or item.get("mfg", ""),
                "discount_text": item.get("lecd", "") or item.get("lcd", ""),
                "booking_url": booking_url,
            })
        parsed.sort(key=lambda x: (x["price"], x["duration_min"], x["transfer_count"]))
        return parsed[:20]

    def _pick_price(self, item: dict) -> Optional[float]:
        for key in ("lecp", "lcp", "lbcp"):
            value = item.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        product_prices = item.get("productPrices") or {}
        values = [float(v) for v in product_prices.values() if isinstance(v, (int, float)) and v > 0]
        return min(values) if values else None

    def _parse_duration_text(self, text: str) -> int:
        total = 0
        if "小时" in text:
            try:
                total += int(text.split("小时", 1)[0].split()[-1]) * 60
            except Exception:
                pass
        if "分钟" in text:
            try:
                mins = text.split("小时")[-1].split("分钟", 1)[0]
                total += int(mins)
            except Exception:
                pass
        return total

    def _parsed_dicts_to_options(
        self, from_city: str, to_city: str, items: List[dict]
    ) -> List[TransportOption]:
        results: List[TransportOption] = []
        for item in items:
            try:
                results.append(TransportOption(
                    from_city=from_city,
                    to_city=to_city,
                    mode=item.get("mode", "flight"),
                    price=float(item.get("price", 999999)),
                    duration_min=int(item.get("duration_min", 99999)),
                    comfort_score=float(item.get("comfort_score", 0.5)),
                    transfer_count=int(item.get("transfer_count", 0)),
                ))
            except Exception:
                continue
        return results[:8]
