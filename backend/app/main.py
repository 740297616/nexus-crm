import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AppException, error_payload
from app.core.logging import configure_logging
from app.core.responses import success_response
from app.db.session import engine

settings = get_settings()
configure_logging(settings.app_debug)
logger = logging.getLogger("nexus_crm.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting %s environment=%s", settings.app_name, settings.app_env)
    yield
    engine.dispose()
    logger.info("stopped %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Nexus CRM modular monolith API foundation.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, request_id, exc.details),
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    details = [{"loc": list(error["loc"]), "message": error["msg"]} for error in exc.errors()]
    return JSONResponse(
        status_code=400,
        content=error_payload("VALIDATION_ERROR", "请求参数校验失败", request_id, details),
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception("unhandled exception request_id=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_payload("INTERNAL_ERROR", "服务暂时不可用", request_id),
        headers={"X-Request-ID": request_id},
    )


@app.get("/healthz", tags=["infrastructure"], summary="Liveness check")
def healthz(request: Request):
    return success_response({"status": "ok"}, request.state.request_id)


@app.get("/readyz", tags=["infrastructure"], summary="Readiness check")
def readyz(request: Request):
    request_id = request.state.request_id
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness check failed request_id=%s", request_id)
        return JSONResponse(
            status_code=503,
            content=error_payload("SERVICE_UNAVAILABLE", "数据库暂时不可用", request_id),
            headers={"X-Request-ID": request_id},
        )
    return success_response({"status": "ready"}, request_id)


app.include_router(api_v1_router, prefix=settings.api_v1_prefix, tags=["v1"])
