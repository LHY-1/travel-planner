from __future__ import annotations

from itertools import permutations
from typing import List

from app.schemas.recommend import RecommendRequest, RecommendResponse, SeedStop, DayDraft


class RecommendService:
    city_profiles = {
        "北京": {"weight": 1.0, "tag": "地标密度高 + 历史核心景点", "cost": 0.92, "has_airport": True, "min_days": 4},
        "西安": {"weight": 1.0, "tag": "历史遗迹 + 城市文化", "cost": 0.72, "has_airport": True, "min_days": 3},
        "上海": {"weight": 0.9, "tag": "都市体验 + 展览 + 夜景", "cost": 0.88, "has_airport": True, "min_days": 2},
        "杭州": {"weight": 0.95, "tag": "西湖 + 城市休闲 + 景观体验", "cost": 0.68, "has_airport": True, "min_days": 2},
        "南京": {"weight": 1.0, "tag": "历史城区 + 博物馆 + 城市步行", "cost": 0.62, "has_airport": True, "min_days": 2},
        "苏州": {"weight": 0.85, "tag": "园林 + 古城 + 轻松慢游", "cost": 0.58, "has_airport": False, "min_days": 2},
        "成都": {"weight": 1.0, "tag": "美食 + 休闲 + 大熊猫 + 都江堰", "cost": 0.65, "has_airport": True, "min_days": 3},
        "重庆": {"weight": 0.9, "tag": "山城夜景 + 美食 + 洪崖洞", "cost": 0.6, "has_airport": True, "min_days": 2},
        "广州": {"weight": 0.82, "tag": "城市美食 + 轻松逛吃", "cost": 0.7, "has_airport": True, "min_days": 2},
        "深圳": {"weight": 0.78, "tag": "现代城市 + 海滨短住", "cost": 0.82, "has_airport": True, "min_days": 1},
        "长沙": {"weight": 0.8, "tag": "网红美食 + 岳麓山 + 娱乐", "cost": 0.55, "has_airport": True, "min_days": 2},
        "武汉": {"weight": 0.82, "tag": "黄鹤楼 + 热干面 + 东湖", "cost": 0.55, "has_airport": True, "min_days": 2},
        "厦门": {"weight": 0.88, "tag": "鼓浪屿 + 海滨 + 文艺", "cost": 0.7, "has_airport": True, "min_days": 2},
        "青岛": {"weight": 0.82, "tag": "海滨 + 啤酒 + 栈桥", "cost": 0.65, "has_airport": True, "min_days": 2},
        "昆明": {"weight": 0.85, "tag": "春城 + 石林 + 滇池", "cost": 0.55, "has_airport": True, "min_days": 2},
        "丽江": {"weight": 0.9, "tag": "古城 + 玉龙雪山 + 束河", "cost": 0.6, "has_airport": True, "min_days": 2},
        "大理": {"weight": 0.88, "tag": "洱海 + 古城 + 苍山", "cost": 0.5, "has_airport": True, "min_days": 2},
        "桂林": {"weight": 0.9, "tag": "漓江 + 阳朔 + 象鼻山", "cost": 0.55, "has_airport": True, "min_days": 2},
        "三亚": {"weight": 0.85, "tag": "海滩 + 度假 + 亚龙湾", "cost": 0.95, "has_airport": True, "min_days": 3},
        "哈尔滨": {"weight": 0.85, "tag": "冰雪大世界 + 中央大街", "cost": 0.65, "has_airport": True, "min_days": 2},
        "天津": {"weight": 0.75, "tag": "五大道 + 美食 + 历史建筑", "cost": 0.55, "has_airport": True, "min_days": 1},
        "石家庄": {"weight": 0.6, "tag": "中转城市", "cost": 0.45, "has_airport": True, "min_days": 0},
    }

    transit_scores = {
        ("上海", "南京"): 0.18, ("上海", "苏州"): 0.08, ("上海", "杭州"): 0.14,
        ("南京", "苏州"): 0.14, ("南京", "杭州"): 0.32, ("苏州", "杭州"): 0.26,
        ("西安", "南京"): 0.88, ("西安", "北京"): 0.5, ("西安", "上海"): 0.9,
        ("杭州", "北京"): 0.82, ("苏州", "北京"): 0.86, ("南京", "北京"): 0.58,
        ("苏州", "西安"): 0.92, ("杭州", "西安"): 0.84, ("南京", "西安"): 0.88,
    }

    hub_access = {
        "苏州": [("上海", 0.12, 0.08), ("南京", 0.18, 0.1)],
    }

    def recommend_seed(self, req: RecommendRequest) -> RecommendResponse:
        end_city = req.end_city or req.start_city
        candidates = [c for c in req.candidate_cities if c not in {req.start_city, end_city}]
        weights = req.weights or {}

        manual_route = [c for c in req.route_order if c and c not in {req.start_city, end_city}]
        
        # 如果没有候选城市且没有手动路线，返回空结果
        if not candidates and not manual_route:
            return RecommendResponse(
                recommended_route=[req.start_city, end_city] if req.start_city != end_city else [req.start_city],
                stops=[],
                daily_draft=[],
                reasons=[],
                debug={"pace": req.pace, "candidate_count": 0, "insufficient_days": False}
            )
        
        if manual_route:
            route_selected = manual_route[:]
        else:
            estimated_transit_days = self._estimate_average_transit_days(req.start_city, end_city, candidates)
            playable_days = max(req.days - estimated_transit_days, 1)
            max_stops = max(1, min(len(candidates), playable_days))
            route_selected = self._build_route(req.start_city, end_city, candidates, max_stops, weights, req.pace)

        route = [req.start_city] + route_selected
        if not route or route[-1] != end_city:
            route.append(end_city)

        city_pool = route_selected[:]

        # 检查推荐天数是否超出总天数，给提示但不裁剪
        # 需要先判断 city_pool 不为空
        all_c = [req.start_city] + city_pool + ([end_city] if not city_pool or end_city != city_pool[-1] else [])
        tc = sum(1.0 if self._transit_score(all_c[i], all_c[i+1]) > 0.7 else (0.5 if self._transit_score(all_c[i], all_c[i+1]) > 0.3 else 0.0) for i in range(len(all_c)-1))
        recommended_total = sum(self.city_profiles.get(c, {}).get("min_days", 2) for c in city_pool)
        trimmed = 0  # 不再裁剪，仅用于提示
        insufficient = (recommended_total + tc) > req.days

        stays = self._allocate_days(city_pool, req.days, req.stay_days_by_city, start_city=req.start_city, end_city=end_city)

        # stops 只保留真正目的地城市，不再把 start_city 塞进去
        stops = [SeedStop(city=city, stay_days=stay_days, reason=self._city_reason(city, req.pace)) for city, stay_days in stays]

        daily_draft: List[DayDraft] = []
        day_no = 1
        for idx, stop in enumerate(stops):
            for local_day in range(stop.stay_days):
                action = "抵达并熟悉城市" if local_day == 0 and idx == 0 else "城市游玩"
                if local_day == 0 and idx > 0:
                    prev_city = stops[idx - 1].city
                    action = f"从 {prev_city} 前往 {stop.city}"
                theme = f"{stop.city} 初到体验" if local_day == 0 else f"{stop.city} 深入游玩"
                daily_draft.append(DayDraft(day=day_no, city=stop.city, theme=theme, action=action))
                day_no += 1

        return RecommendResponse(
            recommended_route=route,
            stops=stops,
            daily_draft=daily_draft,
            reasons=[],
            debug={
                "candidate_count": len(candidates),
                "selected_count": len(route_selected),
                "pace": req.pace,
                "stay_days_by_city": req.stay_days_by_city,
                "insufficient_days": insufficient,
                "recommended_total_days": round(recommended_total + tc, 1),
                "actual_days": req.days,
            },
        )

    def _build_route(self, start_city: str, end_city: str, candidates: List[str], max_stops: int, weights: dict, pace: str) -> List[str]:
        pool = candidates[:]
        if not pool:
            return []

        # 候选太多时，先按城市吸引力/成本/通达性做一轮筛选，而不是机械截前 max_stops 个
        ranked = sorted(
            pool,
            key=lambda c: self._candidate_priority(start_city, end_city, c, weights, pace)
        )
        pool = ranked[:max_stops]

        best_route = pool[:]
        best_score = float('inf')
        for perm in permutations(pool, len(pool)):
            route = list(perm)
            score = self._route_total_score(start_city, end_city, route, weights, pace)
            if score < best_score:
                best_score = score
                best_route = route
        return best_route

    def _route_total_score(self, start_city: str, end_city: str, route: List[str], weights: dict, pace: str) -> float:
        total = 0.0
        current = start_city
        visited = [start_city]
        for idx, city in enumerate(route):
            total += self._edge_score(current, city, weights, pace)
            total += self._backtrack_penalty(visited, city)
            if idx == 0:
                total += self._terminal_airport_penalty(start_city, city, weights)
            visited.append(city)
            current = city
        if current != end_city:
            total += self._edge_score(current, end_city, weights, pace) * 1.15
            total += self._return_penalty(current, end_city)
            total += self._terminal_airport_penalty(current, end_city, weights)
        return total

    def _candidate_priority(self, start_city: str, end_city: str, city: str, weights: dict, pace: str) -> float:
        profile = self.city_profiles.get(city, {"weight": 0.7, "cost": 0.7})
        value = profile.get("weight", 0.7)
        cost = profile.get("cost", 0.7)
        transit_in = self._transit_score(start_city, city)
        transit_out = self._transit_score(city, end_city) if city != end_city else 0.0
        travel_penalty = transit_in + transit_out * 0.8
        pace_bias = -0.08 * value if pace == "relaxed" else (-0.05 * cost if pace == "budget" else 0.0)
        return travel_penalty + cost * 0.5 - value * 0.9 + pace_bias

    def _estimate_average_transit_days(self, start_city: str, end_city: str, candidates: List[str]) -> int:
        if not candidates:
            return 1
        scores = [self._transit_score(start_city, c) for c in candidates]
        scores += [self._transit_score(c, end_city) for c in candidates if c != end_city]
        if not scores:
            return 1
        avg = sum(scores) / len(scores)
        if avg >= 0.7:
            return 2
        if avg >= 0.35:
            return 1
        return 0

    def _edge_score(self, from_city: str, city: str, weights: dict, pace: str) -> float:
        profile = self.city_profiles.get(city, {"weight": 0.7, "cost": 0.7, "has_airport": False})
        transit = self._transit_score(from_city, city)
        cost_w = float(weights.get("cost", 0.4))
        time_w = float(weights.get("time", 0.1))
        exp_w = float(weights.get("experience", 0.35))
        fatigue_w = float(weights.get("fatigue", 0.1))
        comfort_w = float(weights.get("comfort", 0.05))
        pace_bias = 0.15 if pace == "budget" else -0.05 if pace == "relaxed" else 0
        travel_component = transit * (0.8 + time_w + fatigue_w)
        city_cost_component = profile["cost"] * (0.5 + cost_w)
        city_value_discount = profile["weight"] * (0.55 + exp_w + comfort_w)
        airport_penalty = self._airport_penalty(from_city, city, weights)
        return travel_component + city_cost_component - city_value_discount + pace_bias + airport_penalty

    def _airport_penalty(self, from_city: str, to_city: str, weights: dict) -> float:
        from_has_airport = self.city_profiles.get(from_city, {}).get("has_airport", False)
        to_has_airport = self.city_profiles.get(to_city, {}).get("has_airport", False)
        transit = self._transit_score(from_city, to_city)
        if transit < 0.55 or (from_has_airport and to_has_airport):
            return 0.0
        return self._hub_access_penalty(from_city, to_city, weights)

    def _terminal_airport_penalty(self, from_city: str, to_city: str, weights: dict) -> float:
        from_has_airport = self.city_profiles.get(from_city, {}).get("has_airport", False)
        to_has_airport = self.city_profiles.get(to_city, {}).get("has_airport", False)
        transit = self._transit_score(from_city, to_city)
        if transit < 0.55 or (from_has_airport and to_has_airport):
            return 0.0
        return self._hub_access_penalty(from_city, to_city, weights) + 0.35

    def _hub_access_penalty(self, from_city: str, to_city: str, weights: dict) -> float:
        cost_w = float(weights.get("cost", 0.4))
        time_w = float(weights.get("time", 0.1))
        fatigue_w = float(weights.get("fatigue", 0.1))
        candidates = []
        if not self.city_profiles.get(from_city, {}).get("has_airport", False):
            candidates.extend(self.hub_access.get(from_city, []))
        if not self.city_profiles.get(to_city, {}).get("has_airport", False):
            candidates.extend(self.hub_access.get(to_city, []))
        if not candidates:
            return 0.35
        best = min(candidates, key=lambda x: x[1] * (1 + time_w + fatigue_w) + x[2] * (1 + cost_w))
        _, transfer_time_penalty, transfer_cost_penalty = best
        return transfer_time_penalty * (1 + time_w + fatigue_w) + transfer_cost_penalty * (1 + cost_w)

    def _backtrack_penalty(self, visited: List[str], city: str) -> float:
        if city in visited:
            return 1.0
        return 0.0

    def _return_penalty(self, current: str, end_city: str) -> float:
        return self._transit_score(current, end_city) * 0.5

    def _transit_score(self, a: str, b: str) -> float:
        if (a, b) in self.transit_scores:
            return self.transit_scores[(a, b)]
        if (b, a) in self.transit_scores:
            return self.transit_scores[(b, a)]
        return 0.6

    def _allocate_days(self, cities: List[str], total_days: int, overrides: dict, start_city: str = "", end_city: str = ""):
        if not cities:
            return []

        # 估算交通消耗
        all_cities = ([start_city] if start_city else []) + cities + ([end_city] if end_city and end_city != (cities[-1] if cities else "") else [])
        transit_cost_days = 0.0
        for i in range(len(all_cities) - 1):
            sc = self._transit_score(all_cities[i], all_cities[i + 1])
            if sc < 0.3:
                transit_cost_days += 0.0
            elif sc < 0.7:
                transit_cost_days += 0.5
            else:
                transit_cost_days += 1.0

        playable_days = max(int(total_days - transit_cost_days), 0)

        # 用户手动指定的天数优先（只对设置了天数的城市用手动值，其他按权重分配）
        manual_days = {}
        for city in cities:
            manual = int(overrides.get(city, 0) or 0)
            if manual > 0:
                manual_days[city] = manual
        # 如果所有城市都有手动值，全部用手动值
        if len(manual_days) == len(cities):
            return [(city, manual_days[city]) for city in cities]

        if playable_days <= 0:
            return [(city, 1) for city in cities]

        # 每城保底1天，剩余按权重比例分配
        base_days = [1] * len(cities)  # 每城保底1天
        remaining = playable_days - len(cities)

        # 已手动设置天数的城市，从剩余中扣除
        for city, days in manual_days.items():
            idx = cities.index(city) if city in cities else -1
            if idx >= 0:
                base_days[idx] = days
                remaining -= days

        if remaining > 0:
            # 按权重分配剩余天数给未手动设置的城市
            city_weights = {}
            for city in cities:
                profile = self.city_profiles.get(city, {"min_days": 2, "weight": 0.7})
                city_weights[city] = float(profile.get("weight", 0.7))

            total_weight = sum(city_weights.values())
            if total_weight > 0:
                for i, city in enumerate(cities):
                    if city not in manual_days:  # 只给未手动的城市分配
                        extra = round(remaining * city_weights[city] / total_weight)
                        base_days[i] += extra

        # 确保总和等于 playable_days
        current_total = sum(base_days)
        diff = current_total - playable_days
        if diff != 0:
            for _ in range(abs(diff)):
                idx = _ % len(base_days)
                base_days[idx] += (-1 if diff > 0 else 1)

        return [(city, days) for city, days in zip(cities, base_days)]

    def _city_reason(self, city: str, pace: str) -> str:
        profile = self.city_profiles.get(city, {"tag": "适合作为行程中的一站"})
        if pace == "budget":
            return f"{city} 更适合预算优先的路线安排。"
        if pace == "relaxed":
            return f"{city} 适合放慢节奏游玩。"
        return f"{city} 适合均衡型行程，特点是 {profile['tag']}。"
