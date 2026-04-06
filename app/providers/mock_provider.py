from typing import Dict, List, Optional, Tuple
from app.providers.base import BaseTravelProvider
from app.schemas.domain import TransportOption, CityFeature


class MockTravelProvider(BaseTravelProvider):
    async def get_transport_matrix(self, cities: List[str], travel_date: Optional[str] = None) -> Dict[Tuple[str, str], List[TransportOption]]:
        matrix: Dict[Tuple[str, str], List[TransportOption]] = {}
        for i, a in enumerate(cities):
            for j, b in enumerate(cities):
                if a == b:
                    continue
                base = 80 + abs(i - j) * 60
                matrix[(a, b)] = [
                    TransportOption(a, b, "train", float(base), 90 + abs(i - j) * 50, 0.75, 0),
                    TransportOption(a, b, "flight", float(base + 180), 70 + abs(i - j) * 30, 0.82, 0),
                ]
        return matrix

    async def get_city_features(self, cities: List[str], days: int) -> Dict[str, CityFeature]:
        result = {}
        for idx, city in enumerate(cities):
            result[city] = CityFeature(
                city=city,
                experience_score=60 + idx * 8,
                hotel_cost=180 + idx * 40,
                stay_hours=8,
            )
        return result
