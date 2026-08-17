from fastapi import Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


async def starlette_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    if (
        exc.status_code in {401, 403}
        and "text/html" in request.headers.get("accept", "")
    ):
        return RedirectResponse(
            request.url_for("login"),
            status_code=303,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def fastapi_exception_handler(
    request: Request,
    exc: FastAPIHTTPException,
):
    if (
        exc.status_code in {401, 403}
        and "text/html" in request.headers.get("accept", "")
    ):
        return RedirectResponse(
            request.url_for("login"),
            status_code=303,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )