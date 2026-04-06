from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from subprocess import TimeoutExpired
from typing import List, Optional
from urllib.parse import quote

from app.config.settings import BASE_DIR
from app.schemas.domain import TransportOption


class TrainProvider:
    def __init__(self, timeout: float = 35.0):
        self.timeout = timeout
        self.project_dir = Path(BASE_DIR)
        self.script_path = self.project_dir / "scripts" / "search_12306_train.js"

    async def search_single_train(self, from_city: str, to_city: str, travel_date: Optional[str] = None) -> dict:
        # 先查缓存
        from app.services.train_cache import get_cached, set_cached
        cached = get_cached(from_city, to_city, travel_date or "")
        if cached:
            return cached

        # 缓存未命中，查询真实数据
        raw = await self._run_node_script_async([from_city, to_city, travel_date or ""], timeout=45.0)
        parsed = self._parse_results(raw.get("results", []), from_city, to_city, travel_date)
        notices = []
        if raw.get("notes"):
            notices.extend(raw.get("notes", []))
        if not parsed:
            notices.append("当前没有抓到可展示的 12306 结果，可能是映射未补全、页面结构变化或被站点拦截。")

        result = {
            "query": {
                "from_city": from_city,
                "to_city": to_city,
                "travel_date": travel_date,
            },
            "raw": raw,
            "parsed": parsed,
            "count": len(parsed),
            "notices": notices,
            "booking_url": self.build_booking_url(from_city, to_city, travel_date or ""),
        }

        # 只缓存有结果的数据，避免一次失败把空结果锁死好几天
        if parsed:
            set_cached(from_city, to_city, travel_date or "", result)
        return result

    def load_transport_options(self, from_city: str, to_city: str, travel_date: Optional[str] = None) -> List[TransportOption]:
        raw = self._run_node_script([from_city, to_city, travel_date or ""], timeout=45.0)
        parsed = self._parse_transport_options(raw.get("results", []), from_city, to_city)
        parsed.sort(key=lambda x: (x.price, x.duration_min))
        return parsed[:12]

    def build_booking_url(self, from_city: str, to_city: str, travel_date: str) -> str:
        return (
            "https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc"
            f"&fs={quote(from_city)}&ts={quote(to_city)}&date={quote(travel_date)}"
        )

    async def _run_node_script_async(self, args: list[str], timeout: Optional[float] = None) -> dict:
        """异步版本，不阻塞事件循环"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", str(self.script_path), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_dir),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {"error": "timeout", "results": [], "notes": ["12306 查询超时。"]}
            output = (stdout.decode("utf-8", errors="replace").strip() or
                      stderr.decode("utf-8", errors="replace").strip() or "{}")
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"error": "invalid_json", "raw": output[:500], "results": []}
        except Exception as e:
            return {"error": str(e), "results": [], "notes": [f"12306 查询异常: {e}"]}

    def _run_node_script(self, args: list[str], timeout: Optional[float] = None) -> dict:
        try:
            proc = subprocess.run(
                ["node", str(self.script_path), *args],
                cwd=str(self.project_dir),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout or self.timeout,
            )
            output = proc.stdout.strip() or proc.stderr.strip() or "{}"
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"error": "invalid_json", "raw": output, "results": []}
        except TimeoutExpired as e:
            return {
                "error": "timeout",
                "message": str(e),
                "results": [],
                "notes": ["12306 查询超时。"],
            }

    def _parse_results(self, items: list, from_city: str, to_city: str, travel_date: Optional[str]) -> List[dict]:
        parsed = []
        booking_url = self.build_booking_url(from_city, to_city, travel_date or "")
        # 站点名称映射：允许的出发站/到达站前缀
        valid_from_prefixes = self._station_prefixes(from_city)
        valid_to_prefixes = self._station_prefixes(to_city)
        for item in items:
            from_station = item.get("fromStation", "")
            to_station = item.get("toStation", "")
            # 校验站点：出发站必须包含城市名，到达站必须包含目的地城市名
            if not self._is_valid_station(from_station, from_city, valid_from_prefixes):
                continue
            if not self._is_valid_station(to_station, to_city, valid_to_prefixes):
                continue
            seat_name, seat_price = self._pick_train_seat(item.get("seats", {}))
            if seat_price is None:
                continue
            duration_min = self._parse_duration_to_min(item.get("duration"))
            train_no = str(item.get("trainNo", "")).upper()
            parsed.append(
                {
                    "from_city": from_city,
                    "to_city": to_city,
                    "mode": "train",
                    "train_no": train_no,
                    "train_type": self._train_type(train_no),
                    "from_station": item.get("fromStation", ""),
                    "to_station": item.get("toStation", ""),
                    "depart_time": item.get("departTime", ""),
                    "arrive_time": item.get("arriveTime", ""),
                    "duration_text": item.get("duration", ""),
                    "duration_min": duration_min,
                    "arrival_day": item.get("arrivalDay", ""),
                    "seat_type": seat_name,
                    "price": seat_price,
                    "availability": self._pick_availability(item.get("seats", {}), seat_name),
                    "comfort_score": self._comfort_score(train_no),
                    "transfer_count": 0,
                    "booking_url": booking_url,
                }
            )
        # 排序：优先 G 高铁（最快），再 D 动车（较慢但便宜），最后普通车
        # 综合分 = 价格 * 0.5 + 时间(小时) * 5
        def sort_key(x):
            type_penalty = (
                0 if x["train_no"].startswith("G") else
                1 if x["train_no"].startswith("D") else
                4
            )
            hours = x["duration_min"] / 60.0
            score = x["price"] * 0.5 + hours * 5
            return (type_penalty, score)
        parsed.sort(key=sort_key)
        return parsed[:20]

    def _parse_transport_options(self, items: list, from_city: str, to_city: str) -> List[TransportOption]:
        parsed = []
        for item in items:
            _, seat_price = self._pick_train_seat(item.get("seats", {}))
            if seat_price is None:
                continue
            duration_min = self._parse_duration_to_min(item.get("duration"))
            if duration_min <= 0:
                continue
            train_no = str(item.get("trainNo", "")).upper()
            parsed.append(
                TransportOption(
                    from_city=from_city,
                    to_city=to_city,
                    mode="train",
                    price=float(seat_price),
                    duration_min=duration_min,
                    comfort_score=self._comfort_score(train_no),
                    transfer_count=0,
                )
            )
        return parsed

    def classify_train(self, option: TransportOption) -> str:
        train_no = self._extract_train_no_from_option(option)
        return self._train_type(train_no)

    def score_transport_option(self, option: TransportOption, pace: str = "balanced") -> float:
        train_type = self.classify_train(option)
        duration_penalty = option.duration_min * (0.12 if train_type == "high_speed" else 0.18)
        price_penalty = option.price * (0.9 if pace == "budget" else 1.0)
        type_bias = 0 if train_type == "high_speed" else 55
        return price_penalty + duration_penalty + type_bias

    def _extract_train_no_from_option(self, option: TransportOption) -> str:
        return getattr(option, "train_no", "") or ""

    def _train_type(self, train_no: str) -> str:
        if train_no.startswith("G"):
            return "high_speed"
        if train_no.startswith("D"):
            return "intercity"
        return "normal"

    def _station_prefixes(self, city: str) -> list[str]:
        """返回站点名称的有效前缀列表"""
        # 常见城市名变体
        mapping = {
            "上海": ["上海", "上海虹桥", "上海南", "上海西"],
            "苏州": ["苏州", "苏州北", "苏州南", "苏州园区"],
            "西安": ["西安", "西安北", "西安南"],
            "北京": ["北京", "北京南", "北京西", "北京北", "北京东"],
            "南京": ["南京", "南京南", "南京东"],
            "杭州": ["杭州", "杭州东", "杭州南", "杭州西"],
            "成都": ["成都", "成都东", "成都南", "成都西"],
            "广州": ["广州", "广州南", "广州东", "广州北"],
            "深圳": ["深圳", "深圳北", "深圳东", "深圳西"],
        }
        return mapping.get(city, [city])

    def _is_valid_station(self, station: str, city: str, valid_prefixes: list[str]) -> bool:
        """校验站点名称是否属于该城市"""
        if not station:
            return False
        # 站点名必须包含城市名，或者在有效前缀列表中
        if city in station:
            return True
        for prefix in valid_prefixes:
            if station.startswith(prefix) or station == prefix:
                return True
        return False

    def _pick_train_seat(self, seats: dict) -> tuple[str, Optional[float]]:
        """按舒适度优先级选座：高铁/动车选二等座，普速选硬卧/硬座。无座仅当万不得已时选。"""
        # 第一优先级：二等座（高铁/动车首选）
        for seat_name in ["二等座", "一等座", "商务座"]:
            seat = seats.get(seat_name)
            if isinstance(seat, dict):
                price = seat.get("price")
                avail = seat.get("availability", "")
                if isinstance(price, (int, float)) and price > 0 and avail not in ("--",):
                    return seat_name, float(price)
        # 第二优先级：硬座/硬卧（普速首选）
        for seat_name in ["硬座", "硬卧", "软卧", "一等座"]:
            seat = seats.get(seat_name)
            if isinstance(seat, dict):
                price = seat.get("price")
                avail = seat.get("availability", "")
                if isinstance(price, (int, float)) and price > 0 and avail not in ("--",):
                    return seat_name, float(price)
        # 第三优先级：任意有票的座位（排除无效占位符 "--"）
        for seat_name, seat in seats.items():
            if not isinstance(seat, dict):
                continue
            price = seat.get("price")
            avail = seat.get("availability", "")
            if isinstance(price, (int, float)) and price > 0 and avail not in ("--",):
                return seat_name, float(price)
        return "", None

    def _pick_availability(self, seats: dict, seat_name: str) -> str:
        seat = seats.get(seat_name, {}) if isinstance(seats, dict) else {}
        if isinstance(seat, dict):
            return str(seat.get("availability", ""))
        return ""

    def _parse_duration_to_min(self, value: Optional[str]) -> int:
        if not value or ":" not in value:
            return 0
        try:
            hh, mm = value.split(":", 1)
            return int(hh) * 60 + int(mm)
        except Exception:
            return 0

    def _comfort_score(self, train_no: str) -> float:
        if train_no.startswith("G"):
            return 0.88
        if train_no.startswith("D"):
            return 0.8
        return 0.58
