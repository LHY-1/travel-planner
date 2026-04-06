from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.providers.tongcheng_provider import TongchengProvider
from app.providers.train_provider import TrainProvider

router = APIRouter(prefix="/live", tags=["live"])
flight_provider = TongchengProvider()
train_provider = TrainProvider()


class LiveFlightRequest(BaseModel):
    from_city: str
    to_city: str
    date: str


class LiveTrainRequest(BaseModel):
    from_city: str
    to_city: str
    date: str


@router.get("/flight")
async def debug_live_flight(
    from_city: str = Query(...),
    to_city: str = Query(...),
    date: str = Query(...),
):
    data = await flight_provider.search_single_flight(from_city=from_city, to_city=to_city, travel_date=date)
    return data


@router.post("/flight")
async def debug_live_flight_post(req: LiveFlightRequest):
    data = await flight_provider.search_single_flight(from_city=req.from_city, to_city=req.to_city, travel_date=req.date)
    return data


@router.get("/train")
async def debug_live_train(
    from_city: str = Query(...),
    to_city: str = Query(...),
    date: str = Query(...),
):
    data = await train_provider.search_single_train(from_city=from_city, to_city=to_city, travel_date=date)
    return data


@router.post("/train")
async def debug_live_train_post(req: LiveTrainRequest):
    data = await train_provider.search_single_train(from_city=req.from_city, to_city=req.to_city, travel_date=req.date)
    return data


@router.get("/train_cache")
async def train_cache_stats():
    from app.services.train_cache import get_stats
    return get_stats()
