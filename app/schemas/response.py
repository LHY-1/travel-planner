from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class Segment(BaseModel):
    from_city: str
    to_city: str
    mode: str
    price: float
    duration_min: int
    score: float
    source: Optional[str] = None  # realtime | cache | estimate | none
    date: Optional[str] = None
    train_no: Optional[str] = None
    flight_no: Optional[str] = None
    depart_time: Optional[str] = None
    arrive_time: Optional[str] = None
    duration_text: Optional[str] = None
    booking_url: Optional[str] = None


class DailyItem(BaseModel):
    day: int
    date: Optional[str] = None
    city: str
    action: str
    theme: Optional[str] = None
    transport: Optional[Dict[str, Any]] = None  # 当前选中的交通
    transport_options: Optional[List[Dict[str, Any]]] = None  # 所有可选交通
    # 时间线信息
    start_time: Optional[str] = None  # 当天活动开始时间
    end_time: Optional[str] = None    # 当天活动结束时间
    play_hours: Optional[float] = None  # 实际游玩小时数
    # 时间线详情
    timeline: Optional[List[Dict[str, Any]]] = None  # 当天每个时刻的安排


class TimelineEvent(BaseModel):
    time: str  # 时间点 "08:00"
    duration_min: int = 0  # 持续分钟
    event: str  # 事件描述
    type: str = "activity"  # activity | transport | meal | rest


class PlanOption(BaseModel):
    route: List[str]
    total_cost: float
    total_experience: float
    total_time_min: int
    total_score: float
    segments: List[Segment]
    daily_itinerary: List[DailyItem] = []
    meta: Dict[str, Any] = {}


class PlanResponse(BaseModel):
    options: List[PlanOption]
    debug: Dict[str, Any] = {}
    notices: List[str] = []
