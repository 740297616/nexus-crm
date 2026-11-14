from collections.abc import Mapping
from typing import Any


class AppException(Exception):
    """Expected application error that can be returned to an API client."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_payload(
    code: str,
    message: str,
    request_id: str,
    details: Any = None,
) -> Mapping[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "request_id": request_id,
    }
