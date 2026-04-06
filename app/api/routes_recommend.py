from fastapi import APIRouter

from app.schemas.recommend import RecommendRequest
from app.services.recommend_service import RecommendService

router = APIRouter(prefix="/recommend", tags=["recommend"])
service = RecommendService()


@router.post("/itinerary-seed")
async def create_itinerary_seed(req: RecommendRequest):
    return service.recommend_seed(req)
