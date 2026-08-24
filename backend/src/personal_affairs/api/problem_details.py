from typing import NoReturn

from fastapi import Request
from fastapi.responses import JSONResponse

from personal_affairs.api.schemas import ProblemDetails
from personal_affairs.domain.errors import DomainError, ErrorCode


def problem_response(status: int, code: str, detail: str, retryable: bool = False) -> JSONResponse:
    title = code.replace("_", " ").title()
    body = ProblemDetails(status=status, title=title, code=code, detail=detail, retryable=retryable)
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=body.model_dump(mode="json"),
    )


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, DomainError):
        return problem_response(exc.http_status, exc.code, exc.message, exc.retryable)
    return problem_response(500, "INTERNAL_ERROR", str(exc), retryable=True)


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return problem_response(500, "INTERNAL_ERROR", str(exc), retryable=True)


def not_found() -> NoReturn:
    raise DomainError(ErrorCode.NOT_FOUND, "Resource was not found.", 404)
