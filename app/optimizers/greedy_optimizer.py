from typing import Dict, List, Tuple
from app.schemas.request import Weights
from app.schemas.domain import TransportOption, CityFeature
from app.services.scoring_service import ScoringService


class GreedyOptimizer:
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
        remaining = [c for c in candidate_cities if c not in {start_city, end_city}]
        route = [start_city]
        segments = []
        total_cost = 0.0
        total_experience = 0.0
        total_time = 0
        current = start_city

        while remaining:
            scored = []
            for city in remaining:
                options = transport_matrix.get((current, city), [])
                if not options:
                    continue
                best = min(options, key=lambda x: ScoringService.transport_penalty(x, weights))
                projected = total_cost + best.price + city_features[city].hotel_cost
                if projected > budget:
                    continue
                gain = ScoringService.city_gain(city_features[city], weights)
                score = gain - ScoringService.transport_penalty(best, weights)
                scored.append((score, city, best))
            if not scored:
                break
            scored.sort(reverse=True, key=lambda x: x[0])
            _, city, best = scored[0]
            route.append(city)
            segments.append(best)
            total_cost += best.price + city_features[city].hotel_cost
            total_experience += city_features[city].experience_score
            total_time += best.duration_min
            current = city
            remaining.remove(city)

        back_options = transport_matrix.get((current, end_city), [])
        if back_options:
            back = min(back_options, key=lambda x: ScoringService.transport_penalty(x, weights))
            route.append(end_city)
            segments.append(back)
            total_cost += back.price
            total_time += back.duration_min
        elif current != end_city:
            route.append(end_city)

        total_score = total_experience - total_cost
        return {
            "route": route,
            "segments": segments,
            "total_cost": round(total_cost, 2),
            "total_experience": round(total_experience, 2),
            "total_time_min": int(total_time),
            "total_score": round(total_score, 2),
            "strategy": "greedy",
        }
