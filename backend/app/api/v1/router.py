from fastapi import APIRouter, Request

from app.core.responses import success_response
from app.modules.auth.router import router as auth_router
from app.modules.contacts.router import router as contacts_router
from app.modules.customers.router import router as customers_router
from app.modules.followups.router import follow_up_router, reminder_router
from app.modules.organizations.router import router as departments_router
from app.modules.roles.router import router as roles_router
from app.modules.tags.router import router as tags_router
from app.modules.users.router import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(departments_router)
router.include_router(roles_router)
router.include_router(customers_router)
router.include_router(contacts_router)
router.include_router(tags_router)
router.include_router(follow_up_router)
router.include_router(reminder_router)


@router.get("/meta", summary="API metadata")
def api_meta(request: Request):
    request_id = request.state.request_id
    return success_response(
        data={"name": "Nexus CRM API", "version": "v1", "phase": "3"},
        request_id=request_id,
    )
