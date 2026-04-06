from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.providers.base import BaseTravelProvider
from app.providers.mock_provider import MockTravelProvider
from app.providers.tongcheng_provider import TongchengProvider
from app.providers.train_provider import TrainProvider
from app.schemas.domain import CityFeature, TransportOption


class HybridTravelProvider(BaseTravelProvider):
    """
    组合真实/模拟数据：
    - 航班：优先同程实时抓取
    - 火车：优先 12306 实时查询
    - 缺失边：按需回退 mock，尽量减少整单全量 fallback
    """

    def __init__(self):
        self.flight_provider = TongchengProvider()
        self.train_provider = TrainProvider()
        self.mock_provider = MockTravelProvider()

    async def get_transport_matrix(self, cities: List[str], travel_date: Optional[str] = None) -> Dict[Tuple[str, str], List[TransportOption]]:
        matrix: Dict[Tuple[str, str], List[TransportOption]] = {}

        real_flights = await self.flight_provider.get_transport_matrix(cities, travel_date)
        for key, options in real_flights.items():
            matrix[key] = list(options)

        for a in cities:
            for b in cities:
                if a == b:
                    continue
                train_options = self.train_provider.load_transport_options(a, b, travel_date)
                if train_options:
                    matrix.setdefault((a, b), [])
                    matrix[(a, b)].extend(train_options)

        mock_matrix = await self.mock_provider.get_transport_matrix(cities, travel_date)
        for a in cities:
            for b in cities:
                if a == b:
                    continue
                key = (a, b)
                current = matrix.get(key, [])
                if current:
                    real_modes = [x for x in current if x.mode in {"flight", "train"}]
                    if real_modes:
                        current = real_modes
                    current.sort(key=lambda x: (x.price, x.duration_min))
                    matrix[key] = current[:10]
                else:
                    matrix[key] = mock_matrix.get(key, [])

        return matrix

    async def get_city_features(self, cities: List[str], days: int) -> Dict[str, CityFeature]:
        try:
            features = await self.flight_provider.get_city_features(cities, days)
            if features:
                return features
        except Exception:
            pass
        return await self.mock_provider.get_city_features(cities, days)
