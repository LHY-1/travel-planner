from __future__ import annotations

import asyncio
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timedelta
from itertools import permutations

from app.providers.hybrid_provider import HybridTravelProvider
from app.schemas.recommend import RecommendRequest, DayDraft
from app.schemas.request import PlanRequest
from app.schemas.response import DailyItem, PlanResponse, PlanOption, Segment
from app.services.recommend_service import RecommendService


class PlannerService:
    def __init__(self):
        self.provider = HybridTravelProvider()
        self.recommend_service = RecommendService()
        self._train_cache: dict[tuple, list] = {}
        self._flight_cache: dict[tuple, list] = {}
        self._leg_cache: dict[tuple[str, str, str, str], tuple[dict, str | None]] = {}
        self.hub_transfer = {
            "苏州": [
                {"hub": "上海", "duration_min": 45, "price": 60},
                {"hub": "南京", "duration_min": 90, "price": 70},
            ],
        }

    async def create_plan(self, req: PlanRequest):
        notices = []
        provider_name = "混合数据"
        provider_error = None
        self._train_cache = {}  # 每次请求清空内存缓存
        self._leg_cache = {}    # 每次请求清空内存缓存

        try:
            seed = self.recommend_service.recommend_seed(
                RecommendRequest(
                    start_city=req.start_city,
                    end_city=req.end_city,
                    candidate_cities=req.candidate_cities,
                    route_order=req.route_order,
                    stay_days_by_city=req.stay_days_by_city,
                    days=req.days,
                    budget=req.budget,
                    pace=req.pace,
                    travel_date=req.travel_date,
                    weights=req.weights.model_dump(),
                )
            )
            manual_locked = bool(req.route_order or req.stay_days_by_city)
            if manual_locked:
                reorder_notices = ["已按你手动设置的城市顺序/停留天数生成，不再自动重排路线。"]
            else:
                seed, reorder_notices = await self._rerank_seed_with_real_transport(seed, req)
            notices.extend(reorder_notices)
            opts_list, local_notices = await self._build_plan_from_seed(seed, req)
            options = opts_list
            notices.extend(local_notices)
        except Exception as e:
            import os
            tb = traceback.format_exc()
            # Log to file for debugging
            tmp = os.path.join(os.path.dirname(__file__), "..", "runtime_data", "last_error.log")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(f"Exception: {e}\n")
                    f.write(tb)
            except Exception:
                pass
            # Print to stderr so it shows in uvicorn log
            print(f"[PlannerService CRASH] {e}", file=sys.stderr)
            print(tb, file=sys.stderr)
            provider_error = str(e)
            options = [
                PlanOption(
                    route=[req.start_city, req.end_city or req.start_city],
                    total_cost=0,
                    total_experience=0,
                    total_time_min=0,
                    total_score=0,
                    segments=[],
                    daily_itinerary=[],
                    meta={"provider": provider_name, "pace": self._pace_label(req.pace), "strategy": "草案"},
                )
            ]

        debug = {
            "candidate_count": len(req.candidate_cities),
            "provider": provider_name,
            "strategies": [o.meta.get("strategy") for o in options],
            "transport_summary": {
                "pair_count": len(options[0].segments),
                "non_empty_pairs": len(options[0].segments),
                "total_options": len(options[0].segments),
                "coverage": 1 if options[0].segments else 0,
            },
        }
        if provider_error:
            debug["provider_error"] = provider_error
            notices.append("规划生成中有部分步骤失败，当前先返回可展示骨架。")
        return PlanResponse(options=options, debug=debug, notices=notices)

    async def _rerank_seed_with_real_transport(self, seed, req: PlanRequest):
        if req.route_order or req.stay_days_by_city:
            return seed, ["已进入手动优先模式：不自动重排、不自动减城。"]

        stops = list(seed.stops)
        if len(stops) <= 1:
            return seed, []

        original_order = [s.city for s in stops]
        stay_map = {s.city: s.stay_days for s in stops}
        end_city = req.end_city or req.start_city
        all_route_cities = [req.start_city] + [s.city for s in stops]
        if all_route_cities[-1] != end_city:
            all_route_cities.append(end_city)

        if len(all_route_cities) <= 2:
            return seed, []

        pairs = [
            (all_route_cities[i], all_route_cities[i + 1])
            for i in range(len(all_route_cities) - 1)
        ]

        scores: dict[tuple[str, str], float] = {}

        # 并行查询所有城市对的票价（从预查询缓存读取，避免重复 Node 调用）
        async def _score_pair(pair):
            a, b = pair
            best = None
            for key, cached_list in list(self._train_cache.items()):
                if key[0] == a and key[1] == b and cached_list:
                    cand = cached_list[0]
                    if best is None or float(cand.get("price", 999999)) < float(best.get("price", 999999)):
                        best = cand
            price = float(best.get("price", 0)) if best else 0.0
            return (a, b), price

        pair_results = await asyncio.gather(*[_score_pair(p) for p in pairs])
        for (a, b), price in pair_results:
            scores[(a, b)] = price

        ranked = sorted(pairs, key=lambda p: scores[p])
        if ranked != pairs:
            new_stops = [s for s in stops if s.city not in {req.start_city, end_city}]
            new_stops_sorted = sorted(
                new_stops, key=lambda s: ranked.index(s.city) if s.city in [p[1] for p in ranked] else 999
            )
            seed = deepcopy(seed)
            seed.stops = new_stops_sorted
            notices = ["已根据实时交通数据重新排列城市顺序"]
        else:
            notices = []

        estimated_days = sum(max(int(stay_map.get(c, 1)), 1) for c in all_route_cities[1:-1]) + max(
            len(all_route_cities) - 1, 0
        )
        if estimated_days > req.days:
            notices.append(f"按真实交通测算，当前路线需要 {estimated_days} 天（含交通），超出你设置的总天数 {req.days} 天。建议增加天数或减少城市。")

        return seed, notices

    async def _route_real_score(self, route: list[str], stay_map: dict[str, int], req: PlanRequest) -> float:
        """用已有内存缓存估算总票价（无需额外查询）"""
        total = 0.0
        for i, city in enumerate(route[1:], start=1):
            prev_city = route[i - 1]
            best = None
            for key, cached_list in self._train_cache.items():
                if key[0] == prev_city and key[1] == city and cached_list:
                    cand = cached_list[0]
                    if best is None or float(cand.get("price", 999999)) < float(best.get("price", 999999)):
                        best = cand
            if best:
                total += float(best.get("price", 0))
        return total

    async def create_plan_options(
        self, seed, req: PlanRequest
    ) -> tuple[list[PlanOption], list[str]]:
        notices: list[str] = []
        route = [req.start_city] + [stop.city for stop in seed.stops]
        end_city = req.end_city or req.start_city
        if route[-1] != end_city:
            route.append(end_city)

        route_cities = route[1:-1]
        stay_map: dict[str, int] = {}
        for city in route_cities:
            if city in req.stay_days_by_city:
                stay_map[city] = int(req.stay_days_by_city[city])
            else:
                for stop in seed.stops:
                    if stop.city == city:
                        stay_map[city] = max(int(stop.stay_days), 1)
                        break
                else:
                    stay_map[city] = 1

        total_stay = sum(stay_map.get(c, 1) for c in route_cities)
        transit_days = max(len(route) - 1, 0)
        total_days_needed = total_stay + transit_days
        daily_itinerary: list[DailyItem] = []
        current_date = self._parse_date(req.travel_date) if req.travel_date else datetime.now()
        actual_departure_date = current_date

        # ── Step 1: 预先并行查询所有城市对的多个候选日期 ──────────────────────────
        query_pairs: list[tuple[str, str, str]] = []
        cumulative_days = 0
        for i in range(len(route) - 1):
            from_c, to_c = route[i], route[i + 1]
            base_query_date = actual_departure_date + timedelta(days=cumulative_days)
            for offset in range(-1, 3):
                query_date = base_query_date + timedelta(days=offset)
                query_pairs.append((from_c, to_c, query_date.strftime("%Y-%m-%d")))
            if i < len(route_cities):
                city = route_cities[i] if i < len(route_cities) else route_cities[-1]
                cumulative_days += stay_map.get(city, 1)

        # 并行查询所有组合
        async def _query_pair(from_c: str, to_c: str, d: str) -> tuple:
            key = (from_c, to_c, d)
            if key in self._train_cache:
                cached = self._train_cache[key]
                return (from_c, to_c, d, cached, [])
            train_parsed, flight_parsed = [], []
            try:
                t_data = await self.provider.train_provider.search_single_train(from_c, to_c, d)
                train_parsed = t_data.get("parsed", [])
                if train_parsed:
                    self._train_cache[key] = train_parsed
            except Exception:
                pass
            try:
                f_data = await self.provider.flight_provider.search_single_flight(from_c, to_c, d)
                flight_parsed = f_data.get("parsed", [])
                if flight_parsed:
                    # 缓存航班数据
                    self._flight_cache[key] = flight_parsed
            except Exception:
                pass
            return (from_c, to_c, d, train_parsed, flight_parsed)

        query_results = await asyncio.gather(*[_query_pair(*p) for p in query_pairs])

        # 汇总：每个城市对的最佳火车/航班
        pair_best: dict[tuple[str, str], tuple[dict, dict]] = {}
        for from_c, to_c, d, train_parsed, flight_parsed in query_results:
            key = (from_c, to_c)
            if key not in pair_best:
                pair_best[key] = (None, None)
            best_train, best_flight = pair_best[key]
            if train_parsed:
                cand = min(train_parsed, key=lambda x: (float(x.get("price", 999999)), int(x.get("duration_min", 999999))))
                if best_train is None or float(cand.get("price", 999999)) < float(best_train.get("price", 999999)):
                    pair_best[key] = (cand, best_flight)
            if flight_parsed:
                cand = min(flight_parsed, key=lambda x: (float(x.get("price", 999999)), int(x.get("duration_min", 999999))))
                if best_flight is None or float(cand.get("price", 999999)) < float(best_flight.get("price", 999999)):
                    pair_best[key] = (best_train, cand)

        def best_for_pair(from_c: str, to_c: str, leg_idx: int = 0) -> tuple[dict | None, list[dict], str | None]:
            """返回某城市对的最佳交通、所有候选、提示
            leg_idx: 交通段索引，0=第1段（出发），-1=最后一段（返程），其他=中间段
            """
            best_train, best_flight = pair_best.get((from_c, to_c), (None, None))
            
            all_options = []
            if best_train:
                all_options.append(best_train)
            if best_flight:
                all_options.append(best_flight)
            
            # 从火车缓存中获取更多选项
            for key, cached in self._train_cache.items():
                if len(key) >= 2 and key[0] == from_c and key[1] == to_c:
                    for opt in cached:
                        opt_key = (opt.get('train_no'), opt.get('from_city'), opt.get('to_city'))
                        existing_keys = [(o.get('train_no'), o.get('from_city'), o.get('to_city')) for o in all_options]
                        if opt_key not in existing_keys:
                            all_options.append(opt)
            
            # 从航班缓存中获取更多选项
            for key, cached in self._flight_cache.items():
                if len(key) >= 2 and key[0] == from_c and key[1] == to_c:
                    for opt in cached:
                        opt_key = (opt.get('flight_no'), opt.get('from_city'), opt.get('to_city'))
                        existing_keys = [(o.get('flight_no'), o.get('from_city'), o.get('to_city')) for o in all_options]
                        if opt_key not in existing_keys:
                            all_options.append(opt)
            
            if not all_options:
                return None, [], f"{from_c}→{to_c} 交通查询失败"
            
            # 按评分排序
            scored = [(opt, self._score_transport(opt, req.pace, leg_idx)) for opt in all_options]
            scored.sort(key=lambda x: x[1])
            chosen = scored[0][0]
            return chosen, [s[0] for s in scored[:5]], None  # 返回前5个选项

        # ── Step 3: 先查询所有交通段 ─────────────────────────────────────────────
        segment_transports: list[dict] = []
        segment_options: list[list[dict]] = []
        for i in range(len(route) - 1):
            from_c, to_c = route[i], route[i + 1]
            leg_idx = 0 if i == 0 else (-1 if i == len(route) - 2 else i)
            transport, options, notice = best_for_pair(from_c, to_c, leg_idx)
            if transport:
                segment_transports.append(transport)
                segment_options.append(options)
            if notice:
                notices.append(notice)

        # ── Step 4: 生成每日日程 + 计算实际游玩时间 ─────────────────────────────
        # 先计算每个城市的实际游玩小时数
        city_play_hours: dict[str, float] = {}
        for city_idx, city in enumerate(route_cities):
            # 获取到达/出发交通
            inbound_t = segment_transports[city_idx] if city_idx < len(segment_transports) else None
            outbound_t = segment_transports[city_idx + 1] if city_idx + 1 < len(segment_transports) else None

            # 计算到达时间（小时）
            arrive_hour = 0.0  # 默认凌晨到达
            if inbound_t and inbound_t.get("arrive_time"):
                try:
                    parts = inbound_t["arrive_time"].split(":")
                    arrive_hour = float(parts[0]) + float(parts[1]) / 60
                except:
                    arrive_hour = 12.0

            # 计算出发时间（小时）
            depart_hour = 24.0  # 默认午夜出发
            if outbound_t and outbound_t.get("depart_time"):
                try:
                    parts = outbound_t["depart_time"].split(":")
                    depart_hour = float(parts[0]) + float(parts[1]) / 60
                except:
                    depart_hour = 18.0

            # 实际游玩小时数
            days_in_city = stay_map.get(city, 1)
            if city_idx == 0:
                # 第一个城市：从到达时间到出发时间
                play_hours = (days_in_city - 1) * 24 + (depart_hour - arrive_hour)
            else:
                # 后续城市：前一天到达后到出发时间
                play_hours = (days_in_city - 1) * 24 + depart_hour
                # 减去到达那天的剩余时间（如果到达晚）
                if arrive_hour > 12:
                    play_hours -= (24 - arrive_hour)

            city_play_hours[city] = max(0, play_hours)

        # 生成 daily
        daily_itinerary: list[DailyItem] = []
        day_counter = 1

        for city_idx, city in enumerate(route_cities):
            days_in_city = stay_map.get(city, 1)
            
            # 获取这个城市的到达/出发交通
            # route = [北京, 上海, 苏州, 北京]
            # route_cities = [上海, 苏州]（去掉首尾）
            # segment_transports[i] = route[i] → route[i+1]
            #   segment_transports[0] = 北京 → 上海
            #   segment_transports[1] = 上海 → 苏州
            #   segment_transports[2] = 苏州 → 北京
            # 对于 route_cities[city_idx]（中间城市）：
            #   - 它在 route 中的索引 = city_idx + 1
            #   - 到达交通 = segment_transports[city_idx]（前一段）
            #   - 出发交通 = segment_transports[city_idx + 1]（后一段）
            inbound_t = None
            outbound_t = None
            inbound_opts = []
            outbound_opts = []

            # 到达交通 = segment_transports[city_idx]
            if city_idx < len(segment_transports):
                inbound_t = segment_transports[city_idx]
                inbound_opts = segment_options[city_idx] if city_idx < len(segment_options) else []

            # 出发交通 = segment_transports[city_idx + 1]
            if city_idx + 1 < len(segment_transports):
                outbound_t = segment_transports[city_idx + 1]
                outbound_opts = segment_options[city_idx + 1] if city_idx + 1 < len(segment_options) else []

            # 判断到达日是否算游玩
            arrive_play = True
            if inbound_t:
                try:
                    arrive_hour = int(inbound_t.get("arrive_time", "12:00").split(":")[0])
                except:
                    arrive_hour = 12
                if arrive_hour >= 18:
                    arrive_play = False  # 晚上抵达，不算游玩

            # 判断出发日是否算游玩
            depart_play = True
            if outbound_t:
                try:
                    depart_hour = int(outbound_t.get("depart_time", "18:00").split(":")[0])
                except:
                    depart_hour = 18
                if depart_hour < 12:
                    depart_play = False  # 早上出发，不算游玩

            # 计算实际游玩天数
            actual_play_days = days_in_city
            if not arrive_play and city_idx == 0:
                actual_play_days -= 1  # 第一个城市到达日不算
            if not depart_play and city_idx < len(route_cities) - 1:
                actual_play_days -= 1  # 出发日不算

            # 生成每天的记录
            for local_day in range(days_in_city):
                date_str = (actual_departure_date + timedelta(days=day_counter - 1)).strftime("%Y-%m-%d")
                transport = None
                theme = f"{city} 游玩"
                action = "城市游玩"
                
                # 是否是最后一天
                is_last_day = (local_day == days_in_city - 1)
                # 是否是最后城市
                is_last_city = (city_idx == len(route_cities) - 1)
                # 是否是出发日（非最后城市的最后一天）
                is_depart_day = is_last_day and not is_last_city
                # 是否是返程日（最后城市的最后一天）
                is_return_day = is_last_day and is_last_city

                # 第1天：抵达（非第一个城市不显示交通，交通在前一个城市的出发日已显示）
                if local_day == 0:
                    if city_idx == 0 and inbound_t:  # 第一个城市：显示出发地到这里的交通
                        transport = inbound_t
                        try:
                            arrive_hour = int(inbound_t.get("arrive_time", "12:00").split(":")[0])
                        except:
                            arrive_hour = 12
                        if arrive_hour >= 20:
                            theme = "深夜抵达"
                        elif arrive_hour >= 18:
                            theme = "晚上抵达"
                        elif arrive_hour >= 12:
                            theme = "下午抵达"
                        else:
                            theme = "早上抵达"
                        action = f"抵达 {city}"
                    else:  # 中间城市：不显示交通，只标记抵达
                        theme = "抵达"
                        action = f"抵达 {city}"
                
                # 最后一天且非最后城市：出发日（显示交通）
                elif is_depart_day and outbound_t:
                    next_city = route_cities[city_idx + 1]
                    transport = outbound_t
                    try:
                        depart_hour = int(outbound_t.get("depart_time", "18:00").split(":")[0])
                    except:
                        depart_hour = 18
                    if depart_hour >= 20:
                        theme = "深夜出发"
                    elif depart_hour >= 18:
                        theme = "晚上出发"
                    elif depart_hour >= 12:
                        theme = "下午出发"
                    else:
                        theme = "早上出发"
                    action = f"前往 {next_city}"
                
                # 最后一天且是最后城市：返程日（显示交通）
                elif is_return_day and outbound_t:
                    transport = outbound_t
                    try:
                        depart_hour = int(outbound_t.get("depart_time", "12:00").split(":")[0])
                    except:
                        depart_hour = 12
                    if depart_hour >= 18:
                        theme = "游玩后返程"
                    elif depart_hour >= 12:
                        theme = "下午返程"
                    else:
                        theme = "返程"
                    action = f"返回 {req.start_city}"

                # 普通游玩日：不显示时间线（用户觉得啰嗦）
                timeline = []

                # transport_options：第一个城市抵达日显示抵达选项，出发日/返程日显示出发选项
                day_opts = []
                if local_day == 0 and city_idx == 0 and inbound_opts:
                    day_opts = inbound_opts
                elif (is_depart_day or is_return_day) and outbound_opts:
                    day_opts = outbound_opts
                if local_day == 0 and inbound_opts:
                    day_opts = inbound_opts
                elif is_depart_day and outbound_opts:
                    day_opts = outbound_opts

                daily_itinerary.append(DailyItem(
                    day=day_counter,
                    date=date_str,
                    city=city,
                    theme=theme,
                    action=action,
                    transport=transport,
                    transport_options=day_opts,
                    timeline=timeline,
                ))
                day_counter += 1

        # 返程：合并到最后一个城市的最后一天
        # 注意：返程交通已经在上面循环中处理了（当 city_idx == len(route_cities) - 1 时，local_day == days_in_city - 1）
        # 所以这里不需要额外加一天，只需要确保返程交通正确显示
        # 返程交通 = segment_transports[-1]，对应最后一个城市出发
        # 已经在上面循环中处理，这里不需要额外代码

        segments: list[Segment] = []
        total_cost = 0.0
        total_time_min = 0
        for i in range(len(route) - 1):
            from_c, to_c = route[i], route[i + 1]
            if i < len(segment_transports):
                t = segment_transports[i]
                mode_label = self._mode_label(t.get("mode", ""))
                segment = Segment(
                    from_city=from_c,
                    to_city=to_c,
                    mode=mode_label,
                    price=float(t.get("price") or 0),
                    duration_min=int(t.get("duration_min") or 0),
                    score=float(t.get("score") or 0),
                    source=t.get("source"),
                    date=t.get("date") or "",
                    train_no=t.get("train_no") or t.get("flight_no"),
                    depart_time=t.get("depart_time"),
                    arrive_time=t.get("arrive_time"),
                    duration_text=t.get("duration_text"),
                    booking_url=t.get("booking_url"),
                )
                total_cost += float(t.get("price") or 0)
                total_time_min += int(t.get("duration_min") or 0)
                segments.append(segment)

        # Return date
        if req.return_date_end:
            user_return_end = self._parse_date(req.return_date_end)
            min_return_date = actual_departure_date + timedelta(days=total_days_needed)
            if user_return_end and user_return_end < min_return_date:
                notices.append(f"你设置的离宿日期 {req.return_date_end} 早于计划中最早可能的返程日期 {min_return_date.strftime('%Y-%m-%d')}，当前使用的是你指定的返程日期 {req.return_date_end}。")
            else:
                actual_return_end = min_return_date
        else:
            actual_return_end = actual_departure_date + timedelta(days=total_days_needed)

        total_days_used = len(daily_itinerary)
        if total_days_used > req.days:
            notices.append(f"当前行程共 {total_days_used} 天（含交通日），超出你设置的总天数 {req.days} 天。建议增加总天数或减少城市。")

        for idx, item in enumerate(daily_itinerary, start=1):
            item.day = idx

        total_experience = 70.0 * len(daily_itinerary)
        total_score = -(total_cost + total_experience)

        # DEBUG: 检查 segment_transports
        segment_debug = []
        for i, t in enumerate(segment_transports):
            segment_debug.append({
                "idx": i,
                "train_no": t.get("train_no") if t else None,
                "from_station": t.get("from_station") if t else None,
                "to_station": t.get("to_station") if t else None
            })
        
        debug_info = {
            "segment_transports": segment_debug,
            "segment_options_counts": [len(opts) if opts else -1 for opts in segment_options],
            "segment_first_opts": [],
            "daily_opts_sample": []
        }
        for i, opts in enumerate(segment_options):
            if opts and len(opts) > 0:
                debug_info["segment_first_opts"].append({
                    "idx": i,
                    "train_no": opts[0].get("train_no"),
                    "from": opts[0].get("from_station"),
                    "to": opts[0].get("to_station")
                })
        for d in daily_itinerary[:2]:
            if d.transport_options:
                debug_info["daily_opts_sample"].append({
                    "day": d.day,
                    "city": d.city,
                    "first_opt": d.transport_options[0] if d.transport_options else None
                })

        return (
            [PlanOption(
                route=route,
                total_cost=round(total_cost, 2),
                total_experience=round(total_experience, 2),
                total_time_min=int(total_time_min),
                total_score=total_score,
                segments=segments,
                daily_itinerary=daily_itinerary,
                meta={"provider": "混合数据", "pace": self._pace_label(req.pace), "strategy": "timeline-first 日程生成"},
            )],
            notices,
        )

    async def _build_plan_from_seed(self, seed, req: PlanRequest):
        return await self.create_plan_options(seed, req)

    async def _choose_best_transport(
        self, from_city: str, to_city: str, date_str: str | None, pace: str
    ) -> tuple[dict | None, str | None]:
        """查询并选最优交通：先试直飞，再试火车，再试所有候选日，最后 fallback 估算。"""
        if from_city == to_city:
            return None, None

        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        # 只查首日 + 前1天（减少并发压力）
        candidate_dates = [date_str]
        if date_str and len(date_str) == 10:
            try:
                base = datetime.strptime(date_str, "%Y-%m-%d")
                d_prev = (base - timedelta(days=1)).strftime("%Y-%m-%d")
                if d_prev not in candidate_dates:
                    candidate_dates.append(d_prev)
            except Exception:
                pass

        all_train_options: list[dict] = []
        train_notices: list[str] = []

        async def _query_train_one(d: str) -> tuple[list[dict], str | None]:
            key = (from_city, to_city, d)
            if key in self._train_cache:
                cached = self._train_cache[key]
                return cached, None
            try:
                data = await self.provider.train_provider.search_single_train(from_city, to_city, d)
                parsed = data.get("parsed", [])
                if parsed:
                    self._train_cache[key] = parsed
                else:
                    self._train_cache[key] = []
                    notes = data.get("notes") or []
                    for note in notes:
                        if "失败" in note or "超时" in note or "异常" in note or "timeout" in note.lower():
                            return [], f"{from_city}→{to_city} 火车查询失败（{notes[0]}）"
                return parsed, None
            except Exception:
                return [], f"{from_city}→{to_city} 火车查询异常"

        train_results = await asyncio.gather(*[_query_train_one(d) for d in candidate_dates])
        for parsed, notice in train_results:
            all_train_options.extend(parsed)
            if notice and not train_notices:
                train_notices.append(notice)

        best_train: dict | None = None
        if all_train_options:
            best_train = min(
                all_train_options,
                key=lambda x: (float(x.get("price") or 999999), int(x.get("duration_min") or 999999)),
            )

        all_flight_options: list[dict] = []
        flight_notices: list[str] = []

        async def _query_flight_one(d: str) -> tuple[list[dict], str | None]:
            try:
                data = await self.provider.flight_provider.search_single_flight(from_city, to_city, d)
                parsed = data.get("parsed", [])
                if not parsed:
                    notes = data.get("notes") or []
                    if notes:
                        return [], f"{from_city}→{to_city} 实时查询未命中。"
                return parsed, None
            except Exception:
                return [], None

        flight_results = await asyncio.gather(*[_query_flight_one(d) for d in candidate_dates])
        for parsed, notice in flight_results:
            all_flight_options.extend(parsed)
            if notice and not flight_notices:
                flight_notices.append(notice)

        best_flight: dict | None = None
        if all_flight_options:
            best_flight = min(
                all_flight_options,
                key=lambda x: (float(x.get("price") or 999999), int(x.get("duration_min") or 999999)),
            )

        all_options: list[tuple] = []
        if best_train:
            all_options.append((best_train, self._score_transport(best_train, pace)))
        if best_flight:
            all_options.append((best_flight, self._score_transport(best_flight, pace)))

        if not all_options:
            fallback = await self.provider.mock_provider.get_transport_matrix([from_city, to_city], date_str)
            options = fallback.get((from_city, to_city), []) if isinstance(fallback, dict) else []
            if options:
                best = sorted(options, key=lambda x: (x.price, x.duration_min))[0]
                return {
                    "mode": self._mode_label(best.mode),
                    "source": "estimate",
                    "price": best.price,
                    "duration_min": best.duration_min,
                    "comfort_score": best.comfort_score,
                    "date": date_str,
                }, None
            train_notice = train_notices[0] if train_notices else None
            flight_notice = flight_notices[0] if flight_notices else None
            notice = train_notice or flight_notice or f"{from_city}→{to_city} 交通查询失败（1 天均无结果）"
            return None, notice

        best, score = min(all_options, key=lambda x: x[1])
        return best, None

    async def _choose_transport(self, from_city: str, to_city: str, date_str: str | None, pace: str, explicit_dates: list[str] | None = None):
        """旧版兼容接口，内部委托"""
        return await self._choose_best_transport(from_city, to_city, date_str, pace)

    def _score_transport(self, t: dict, pace: str = "balanced", leg_idx: int = 0) -> float:
        price = float(t.get("price") or 0)
        duration_min = int(t.get("duration_min") or 0)
        comfort = float(t.get("comfort_score") or 0.5)
        source = t.get("source", "")

        if pace == "budget":
            price_penalty = price * 1.4
            duration_penalty = duration_min * 0.08
        elif pace == "relaxed":
            price_penalty = price * 0.6
            duration_penalty = duration_min * 0.3
        else:
            price_penalty = price * 1.0
            duration_penalty = duration_min * 0.15

        comfort_bonus = (1.0 - comfort) * 40
        realtime_bonus = -20 if source == "realtime" else 0

        # 航班速度优势：长距离优先选航班
        # 航班被时间惩罚严重抵消了速度优势，需要足够大的奖励来平衡
        is_flight = t.get("mode") == "flight" or t.get("flight_no")
        flight_bonus = 0
        if is_flight and duration_min > 0:
            # 长距离航班基础奖励 - 力度足够大让航班在长距离时优先于慢速火车
            flight_bonus = -180
            # 距离越远，航班优势越大
            if duration_min < 120:  # 飞行时间 < 2小时（短途）
                flight_bonus = -50
            elif duration_min > 300:  # 飞行时间 > 5小时（超长途）
                flight_bonus = -250
            elif duration_min > 180:  # 飞行时间 3-5小时（长途）
                flight_bonus = -200

        # 时间评分：根据交通段类型调整
        # leg_idx: 0=第1段（出发），-1=返程，其他=中间段
        time_score = 0
        arrive_time = t.get("arrive_time", "")
        depart_time = t.get("depart_time", "")

        if leg_idx == 0:
            # 第1段交通：希望下午抵达，当天可玩
            # 深夜抵达 = 浪费第1天白天
            if arrive_time:
                try:
                    arrive_hour = int(arrive_time.split(":")[0])
                    if arrive_hour >= 22:
                        time_score += 150  # 深夜抵达，重惩罚（浪费第1天）
                    elif arrive_hour >= 18:
                        time_score += 80   # 晚上抵达，惩罚
                    elif arrive_hour >= 14:
                        time_score += 20   # 下午抵达，轻惩罚
                    elif arrive_hour >= 10:
                        time_score -= 30   # 上午抵达，加分
                    else:
                        time_score -= 50   # 早上抵达，大加分
                except:
                    pass
        elif leg_idx == -1:
            # 返程：希望晚上出发，白天玩完
            if depart_time:
                try:
                    depart_hour = int(depart_time.split(":")[0])
                    if depart_hour >= 20:
                        time_score -= 50   # 晚上出发，加分
                    elif depart_hour >= 18:
                        time_score -= 30   # 傍晚出发，加分
                    elif depart_hour >= 14:
                        time_score += 10   # 下午出发，轻惩罚
                    else:
                        time_score += 80   # 早上/中午出发，惩罚
                except:
                    pass
        else:
            # 中间段：希望晚上出发、早上抵达，不浪费白天
            if depart_time:
                try:
                    depart_hour = int(depart_time.split(":")[0])
                    if depart_hour >= 20:
                        time_score -= 50   # 晚上出发，加分
                    elif depart_hour >= 18:
                        time_score -= 30   # 傍晚出发，加分
                    elif depart_hour < 10:
                        time_score += 100  # 早上出发，重惩罚
                    elif depart_hour < 14:
                        time_score += 50   # 中午出发，惩罚
                except:
                    pass
            if arrive_time:
                try:
                    arrive_hour = int(arrive_time.split(":")[0])
                    if arrive_hour >= 22 or arrive_hour < 6:
                        time_score -= 30   # 深夜抵达，加分
                    elif arrive_hour < 10:
                        time_score -= 50   # 早上抵达，大加分
                    elif arrive_hour < 14:
                        time_score += 10   # 中午抵达，轻惩罚
                    else:
                        time_score += 50   # 下午/晚上抵达，惩罚
                except:
                    pass

        # 省钱模式：夜间卧铺加分（省一晚酒店钱）
        if pace == "budget" and depart_time:
            try:
                depart_hour = int(depart_time.split(":")[0])
                # 晚上出发、早上到达的夜间车
                if depart_hour >= 20 or depart_hour < 6:
                    # 检查是否是卧铺（D字头动卧或普通卧铺）
                    train_no = t.get("train_no", "")
                    if train_no.startswith("D") or "卧" in str(t.get("seat_type", "")):
                        time_score -= 50  # 省钱模式夜间卧铺大加分
            except:
                pass

        return price_penalty + duration_penalty - comfort_bonus + realtime_bonus + time_score + flight_bonus

    def _candidate_dates(self, start: str | None, end: str | None, travel_date: str | None) -> list[str]:
        dates: list[str] = []
        for d_str in [travel_date, start, end]:
            if d_str and len(d_str) == 10:
                dates.append(d_str)
        seen: set[str] = set()
        unique: list[str] = []
        for d in dates:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        return unique or [travel_date or datetime.now().strftime("%Y-%m-%d")]

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str or len(date_str) < 10:
            return None
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return None

    def _format_date(self, base_date, offset: int):
        if not base_date:
            return None
        try:
            return (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        except Exception:
            return None

    def _parse_duration(self, text: str | None) -> int:
        if not text:
            return -1
        try:
            return int(text.replace("小时", "").replace("分钟", "").strip())
        except Exception:
            return -1

    def _mode_label(self, mode: str) -> str:
        return {"train": "火车", "flight": "航班", "fallback": "未测到", "bus": "巴士"}.get(mode, mode)

    def _pace_label(self, pace: str) -> str:
        return {"balanced": "均衡", "budget": "省钱模式", "relaxed": "宽松"}.get(pace, pace)

    def _train_type_label(self, train_type: str | None) -> str:
        return {"high_speed": "高铁", "normal": "普速", "direct": "直达"}.get(train_type or "", "普通")

    def _build_timeline(self, transport: dict | None, theme: str, city: str) -> list[dict]:
        """生成当天的时间线"""
        timeline = []
        
        if transport:
            # 有交通
            depart_time = transport.get("depart_time", "")
            arrive_time = transport.get("arrive_time", "")
            mode = transport.get("mode", "")
            train_no = transport.get("train_no") or transport.get("flight_no", "")
            from_city = transport.get("from_city", "")
            to_city = transport.get("to_city", "")
            
            if depart_time and "抵达" not in theme and "返程" not in theme:
                # 出发交通
                timeline.append({
                    "time": depart_time,
                    "duration_min": transport.get("duration_min", 0),
                    "event": f"{'🚄' if mode == '火车' else '✈️'} {train_no} {from_city}→{to_city}",
                    "type": "transport"
                })
                if arrive_time:
                    timeline.append({
                        "time": arrive_time,
                        "duration_min": 0,
                        "event": f"抵达 {to_city}",
                        "type": "activity"
                    })
            elif arrive_time and ("抵达" in theme or city == to_city):
                # 到达交通
                timeline.append({
                    "time": arrive_time,
                    "duration_min": 0,
                    "event": f"抵达 {city}",
                    "type": "activity"
                })
        
        # 根据主题添加游玩时间
        if "游玩" in theme or "抵达" in theme:
            # 找到游玩开始时间
            start_hour = 9
            if transport and transport.get("arrive_time"):
                try:
                    parts = transport["arrive_time"].split(":")
                    arr_h = int(parts[0])
                    if arr_h >= 8:
                        start_hour = arr_h + 1  # 到达后1小时开始玩
                except:
                    pass
            
            timeline.append({
                "time": f"{start_hour:02d}:00",
                "duration_min": 120,
                "event": f"{city} 游览",
                "type": "activity"
            })
            timeline.append({
                "time": f"{start_hour + 2:02d}:00",
                "duration_min": 60,
                "event": "午餐",
                "type": "meal"
            })
            timeline.append({
                "time": f"{start_hour + 3:02d}:00",
                "duration_min": 180,
                "event": f"{city} 游览",
                "type": "activity"
            })
        
        # 按时间排序
        timeline.sort(key=lambda x: x["time"])
        return timeline
