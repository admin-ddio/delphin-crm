"""Application factory.

Dev:  uvicorn app.main:create_app --factory --reload
Prod: gunicorn 'app.main:create_app()' -k uvicorn.workers.UvicornWorker
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.health import router as health_router
from app.api.router import API_PREFIX, OPENAPI_TAGS, api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.core.idempotency import IDEMPOTENCY_HEADER
from app.core.logging import configure_logging, get_logger, instrument
from app.core.middleware import BodySizeLimitMiddleware, CSRFMiddleware, SecurityHeadersMiddleware
from app.core.request_id import REQUEST_ID_HEADER, RequestContextMiddleware
from app.db.session import create_engine, create_sessionmaker
from app.modules.jobs.router import RUN_PATH as JOBS_RUN_PATH

DOCS_PATH = "/api/docs"
OPENAPI_PATH = f"{API_PREFIX}/openapi.json"


def operation_id(route: APIRoute) -> str:
    """Stable operationId `<tag>_<function>` so the generated TS client has readable names."""
    tag = str(route.tags[0]) if route.tags else "default"
    return f"{tag}_{route.name}"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    if settings.is_production and not settings.cookies_secure:
        get_logger(__name__).warning(
            "insecure_session_cookies",
            detail="SESSION_COOKIE_SECURE=false: session cookies travel over plain http. "
            "Temporary only; serve over HTTPS and remove the setting.",
        )

    engine = create_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url=OPENAPI_PATH if settings.docs_enabled else None,
        docs_url=DOCS_PATH if settings.docs_enabled else None,
        redoc_url=None,
        openapi_tags=OPENAPI_TAGS,
        generate_unique_id_function=operation_id,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)

    install_exception_handlers(app, settings)
    app.include_router(health_router)
    app.include_router(api_router)

    # Middleware: added innermost first, so the last one added runs first.
    app.add_middleware(
        CSRFMiddleware,
        session_cookie=settings.session_cookie_name,
        csrf_cookie=settings.csrf_cookie_name,
        csrf_header=settings.csrf_header_name,
        exempt_paths={JOBS_RUN_PATH},
    )
    if settings.cors_origins and not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                settings.csrf_header_name,
                REQUEST_ID_HEADER,
                IDEMPOTENCY_HEADER,
            ],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(
        SecurityHeadersMiddleware,
        production=settings.is_production,
        docs_path=DOCS_PATH if settings.docs_enabled else None,
    )
    app.add_middleware(RequestContextMiddleware)

    instrument(app)
    return app
