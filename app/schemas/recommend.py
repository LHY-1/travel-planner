from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    start_city: str
    end_city: Optional[str] = None
    candidate_cities: List[str] = Field(default_factory=list)
    route_order: List[str] = Field(default_factory=list)
    stay_days_by_city: Dict[str, int] = Field(default_factory=dict)
    days: int = 4
    budget: float = 3000.0
    pace: str = "balanced"
    travel_date: Optional[str] = None
    weights: Dict[str, float] = Field(default_factory=dict)


class SeedStop(BaseModel):
    city: str
    stay_days: int
    reason: str


class DayDraft(BaseModel):
    day: int
    city: str
    theme: str
    action: str


class RecommendResponse(BaseModel):
    recommended_route: List[str]
    stops: List[SeedStop]
    daily_draft: List[DayDraft]
    reasons: List[str]
    debug: Dict[str, Any] = {}
