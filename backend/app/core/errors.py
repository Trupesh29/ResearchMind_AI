import logging
from enum import Enum
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("researchmind.errors")


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    PDF_UNREADABLE = "PDF_UNREADABLE"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    PAPER_NOT_READY = "PAPER_NOT_READY"
    DUPLICATE_PAPER = "DUPLICATE_PAPER"
    INDEX_BUILDING = "INDEX_BUILDING"
    NO_ACTIVE_INDEX = "NO_ACTIVE_INDEX"
    NAME_CONFLICT = "NAME_CONFLICT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNPROCESSABLE = "UNPROCESSABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    SERVICE_BUSY = "SERVICE_BUSY"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class AppException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def build_error_envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or "",
        }
    }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    logger.warning(
        f"AppException: {exc.code.value} - {exc.message} (status: {exc.status_code})",
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_envelope(
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")

    # Map status code to standard ErrorCode
    code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.UNAUTHENTICATED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.NAME_CONFLICT,
        413: ErrorCode.FILE_TOO_LARGE,
        422: ErrorCode.UNPROCESSABLE,
        429: ErrorCode.RATE_LIMITED,
        501: ErrorCode.NOT_IMPLEMENTED,
        502: ErrorCode.LLM_UNAVAILABLE,
        503: ErrorCode.SERVICE_BUSY,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    message = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."
    details = exc.detail if isinstance(exc.detail, dict) else {}

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_envelope(
            code=code.value,
            message=message,
            details=details,
            request_id=request_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append({"field": loc, "issue": msg})

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=build_error_envelope(
            code=ErrorCode.INVALID_REQUEST.value,
            message="Request validation failed. Please check the submitted fields.",
            details={"validation_errors": errors},
            request_id=request_id,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    logger.exception(
        f"Unhandled exception during request processing: {exc}",
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=build_error_envelope(
            code=ErrorCode.INTERNAL_ERROR.value,
            message="An unexpected internal server error occurred. Please try again later.",
            details={},
            request_id=request_id,
        ),
    )
