from math import inf
from typing import Dict, List, Optional, Tuple
from app.schemas.request import Weights
from app.schemas.domain import TransportOption, CityFeature
from app.services.scoring_service import ScoringService


class DPOptimizer:
    def optimize(
        self,
        start_city: str,
        end_city: str,
        candidate_cities: List[str],
        transport_matrix: Dict[Tuple[str, str], List[TransportOption]],
        city_features: Dict[str, CityFeature],
        weights: Weights,
        budget: float,
    ):
        cities = [c for c in candidate_cities if c not in {start_city, end_city}]
        n = len(cities)
        if n == 0:
            return self._direct_plan(start_city, end_city, transport_matrix, weights)

        dp = [[-inf] * n for _ in range(1 << n)]
        parent: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
        seg_choice: Dict[Tuple[int, int], TransportOption] = {}
        spend = [[inf] * n for _ in range(1 << n)]

        for i, city in enumerate(cities):
            option = self._best_option(start_city, city, transport_matrix, weights)
            if option is None:
                continue
            gain = ScoringService.city_gain(city_features[city], weights)
            score = gain - ScoringService.transport_penalty(option, weights)
            mask = 1 << i
            dp[mask][i] = score
            spend[mask][i] = option.price + city_features[city].hotel_cost
            parent[(mask, i)] = None
            seg_choice[(mask, i)] = option

        for mask in range(1 << n):
            for i in range(n):
                if dp[mask][i] == -inf:
                    continue
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    a = cities[i]
                    b = cities[j]
                    option = self._best_option(a, b, transport_matrix, weights)
                    if option is None:
                        continue
                    next_mask = mask | (1 << j)
                    next_spend = spend[mask][i] + option.price + city_features[b].hotel_cost
                    if next_spend > budget:
                        continue
                    next_score = dp[mask][i] + ScoringService.city_gain(city_features[b], weights) - ScoringService.transport_penalty(option, weights)
                    if next_score > dp[next_mask][j]:
                        dp[next_mask][j] = next_score
                        spend[next_mask][j] = next_spend
                        parent[(next_mask, j)] = (mask, i)
                        seg_choice[(next_mask, j)] = option

        best = None
        best_score = -inf
        best_spend = inf
        for mask in range(1 << n):
            for i in range(n):
                if dp[mask][i] == -inf:
                    continue
                last_city = cities[i]
                back = self._best_option(last_city, end_city, transport_matrix, weights)
                if back is None:
                    continue
                total_score = dp[mask][i] - ScoringService.transport_penalty(back, weights)
                total_spend = spend[mask][i] + back.price
                if total_spend <= budget and total_score > best_score:
                    best_score = total_score
                    best_spend = total_spend
                    best = (mask, i, back)

        if best is None:
            return self._direct_plan(start_city, end_city, transport_matrix, weights)

        mask, idx, back = best
        route = [end_city]
        segments = [back]
        cur = (mask, idx)
        while cur in parent:
            route.append(cities[cur[1]])
            prev = parent[cur]
            if prev is None:
                segments.append(seg_choice[cur])
                break
            segments.append(seg_choice[cur])
            cur = prev
        route.append(start_city)
        route.reverse()
        segments.reverse()

        total_experience = sum(city_features[c].experience_score for c in route if c in city_features)
        total_time = sum(s.duration_min for s in segments)
        return {
            "route": route,
            "segments": segments,
            "total_cost": round(best_spend, 2),
            "total_experience": round(total_experience, 2),
            "total_time_min": int(total_time),
            "total_score": round(best_score, 2),
        }

    def _best_option(self, a, b, matrix, weights):
        options = matrix.get((a, b), [])
        if not options:
            return None
        return min(options, key=lambda x: ScoringService.transport_penalty(x, weights))

    def _direct_plan(self, start_city, end_city, matrix, weights):
        option = self._best_option(start_city, end_city, matrix, weights)
        if option is None:
            return {
                "route": [start_city, end_city],
                "segments": [],
                "total_cost": 0,
                "total_experience": 0,
                "total_time_min": 0,
                "total_score": 0,
            }
        score = -ScoringService.transport_penalty(option, weights)
        return {
            "route": [start_city, end_city],
            "segments": [option],
            "total_cost": round(option.price, 2),
            "total_experience": 0,
            "total_time_min": option.duration_min,
            "total_score": round(score, 2),
        }
