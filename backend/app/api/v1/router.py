from fastapi import APIRouter, Request

from app.core.responses import success_response
from app.modules.auth.router import router as auth_router

router = APIRouter()
router.include_router(auth_router)


@router.get("/meta", summary="API metadata")
def api_meta(request: Request):
    request_id = request.state.request_id
    return success_response(
        data={"name": "Nexus CRM API", "version": "v1", "phase": "0"},
        request_id=request_id,
    )
