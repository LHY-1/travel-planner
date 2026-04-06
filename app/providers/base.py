from typing import Dict, List, Optional, Tuple
from app.schemas.domain import TransportOption, CityFeature


class BaseTravelProvider:
    async def get_transport_matrix(self, cities: List[str], travel_date: Optional[str] = None) -> Dict[Tuple[str, str], List[TransportOption]]:
        raise NotImplementedError

    async def get_city_features(self, cities: List[str], days: int) -> Dict[str, CityFeature]:
        raise NotImplementedError
