from typing import Any

from fastapi.responses import JSONResponse


def success_payload(
    data: Any,
    request_id: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "meta": meta,
        "request_id": request_id,
    }


def success_response(
    data: Any,
    request_id: str,
    meta: dict[str, Any] | None = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=success_payload(data=data, request_id=request_id, meta=meta),
        headers={"X-Request-ID": request_id},
    )
