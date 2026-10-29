"""Application entry point: `uvicorn app.main:app --reload`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.settings import load_env_file
from app.posters import POSTER_DIR
from app.routers import lookup, titles
from app.templating import STATIC_DIR, templates

logger = logging.getLogger(__name__)

load_env_file()  # optional API keys from .env, e.g. TMDB_API_KEY


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="MediaGala", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/posters", StaticFiles(directory=POSTER_DIR), name="posters")
app.include_router(titles.router)
app.include_router(lookup.router)


def render_error(request: Request, status_code: int, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "error.html", {"status_code": status_code, "message": message}, status_code=status_code
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    # Starlette's generic "Not Found" (unknown URL) gets a friendlier wording.
    message = "This page doesn't exist." if exc.detail == "Not Found" else str(exc.detail)
    return render_error(request, exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> HTMLResponse:
    # e.g. /titles/abc/edit — a malformed URL, not a form error.
    return render_error(request, status.HTTP_400_BAD_REQUEST, "That request doesn't look right.")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return render_error(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong on our side.")
