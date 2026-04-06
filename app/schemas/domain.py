from dataclasses import dataclass


@dataclass
class TransportOption:
    from_city: str
    to_city: str
    mode: str
    price: float
    duration_min: int
    comfort_score: float
    transfer_count: int = 0


@dataclass
class CityFeature:
    city: str
    experience_score: float
    hotel_cost: float
    stay_hours: int
