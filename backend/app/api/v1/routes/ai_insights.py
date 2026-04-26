"""
PulseDesk AI Insights routes.
Route handlers delegate to the AI service layer and remain provider-agnostic.

NOTE: Burnout Risk and Activity Patterns endpoints have been removed
as the frontend no longer uses them. The service methods are retained
for potential future API access but are not exposed as routes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import (
    AIDiagnosticsResponse,
    AnomalyRecommendationResponse,
    ChatRequest,
    ChatResponse,
    WorkRecommendationsResponse,
)
from app.ai.service import ai_insights_service
from app.api.v1.routes.auth import require_admin_read
from app.db.session import get_db

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin_read),
):
    return await ai_insights_service.chat(req, db)


@router.get("/work-recommendations/{employee_id}", response_model=WorkRecommendationsResponse)
async def work_recommendations(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin_read),
):
    return await ai_insights_service.work_recommendations(employee_id, db)


@router.get("/anomaly-recommendation/{employee_id}", response_model=AnomalyRecommendationResponse)
async def anomaly_recommendation(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin_read),
):
    return await ai_insights_service.anomaly_recommendation(employee_id, db)


@router.get("/diagnostics/data-status", response_model=AIDiagnosticsResponse)
async def data_status(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin_read),
):
    return await ai_insights_service.diagnostics(db)
