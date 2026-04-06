from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.api.routes_plan import router as plan_router
from app.api.routes_health import router as health_router
from app.api.routes_live import router as live_router
from app.api.routes_recommend import router as recommend_router

app = FastAPI(title="Travel Planner Optimizer", version="1.3.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(plan_router)
app.include_router(health_router)
app.include_router(live_router)
app.include_router(recommend_router)

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/")
def root():
    if (FRONTEND_DIR / "index.html").exists():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
    return {"ok": True, "service": "travel_planner"}
