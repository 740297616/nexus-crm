from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.common.schemas import ApiSuccess
from app.core.responses import success_response
from app.modules.auth.model import User
from app.modules.dashboard.schema import DashboardSummaryResponse
from app.modules.dashboard.service import get_dashboard_summary
from app.modules.roles.dependencies import require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    summary="Get scoped CRM workbench statistics",
    description=(
        "Permission: dashboard:read. Personal and management metrics are calculated with "
        "database aggregates and the authenticated user's data scope. Trends use UTC dates."
    ),
    response_model=ApiSuccess[DashboardSummaryResponse],
)
def get_summary(
    request: Request,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("dashboard:read")),
):
    summary = get_dashboard_summary(
        db,
        actor=actor,
        start_date=start_date,
        end_date=end_date,
    )
    return success_response(summary.model_dump(mode="json"), request.state.request_id)
