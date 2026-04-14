from fastapi import APIRouter
from app.api.v1.routes import auth, employees, devices, agent, analytics, screenshots, ws, enrollment
from app.api.v1.routes import reports
from app.api.v1.routes.blocker import router as blocker_router
from app.api.v1.routes.ai_insights import router as ai_router
from app.api.v1.routes.actions import router as actions_router
from app.api.v1.routes.settings import router as settings_router

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(devices.router)
api_router.include_router(agent.router)
api_router.include_router(analytics.router)
api_router.include_router(screenshots.router)
api_router.include_router(ws.router)
api_router.include_router(reports.router)
api_router.include_router(blocker_router)
api_router.include_router(ai_router)
api_router.include_router(actions_router)
api_router.include_router(enrollment.router)
api_router.include_router(settings_router)
