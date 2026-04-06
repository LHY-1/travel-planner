from fastapi import APIRouter
from app.schemas.request import PlanRequest
from app.services.planner_service import PlannerService
import traceback

router = APIRouter(prefix="/plan", tags=["plan"])

# 每次请求创建新实例，避免缓存问题
@router.post("")
async def create_plan(req: PlanRequest):
    try:
        service = PlannerService()  # 每次创建新实例
        result = await service.create_plan(req)
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "options": [],
            "debug": {"provider_error": str(e)},
            "notices": [f"API Error: {e}"]
        }
