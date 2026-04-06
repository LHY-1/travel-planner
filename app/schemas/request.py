from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class Weights(BaseModel):
    cost: float = 0.4
    experience: float = 0.35
    time: float = 0.1
    fatigue: float = 0.1
    comfort: float = 0.05


class PlanRequest(BaseModel):
    start_city: str
    end_city: Optional[str] = None
    candidate_cities: List[str] = Field(default_factory=list)
    must_visit: List[str] = Field(default_factory=list)
    route_order: List[str] = Field(default_factory=list)
    stay_days_by_city: Dict[str, int] = Field(default_factory=dict)
    days: int = 3
    budget: float = 3000.0
    weights: Weights = Weights()
    pace: str = "balanced"
    travel_date: Optional[str] = None
    departure_date_start: Optional[str] = None
    departure_date_end: Optional[str] = None
    return_date_start: Optional[str] = None
    return_date_end: Optional[str] = None
