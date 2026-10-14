import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, router
from app.core.config import Settings
from app.core.container import Container, build_container
from app.core.logging import configure_logging, correlation_id_var

CORRELATION_HEADER = "X-Correlation-ID"


def create_app(settings: Optional[Settings] = None, container: Optional[Container] = None) -> FastAPI:
    settings = settings or (container.settings if container else Settings())
    configure_logging(settings.log_level, settings.datacenter)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container or build_container(settings)
        yield
        app.state.container.close()

    app = FastAPI(title="BC Workflows Agent Platform", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", CORRELATION_HEADER, "X-Banker-Id"],
        expose_headers=[CORRELATION_HEADER],
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        value = request.headers.get(CORRELATION_HEADER) or uuid.uuid4().hex
        token = correlation_id_var.set(value)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[CORRELATION_HEADER] = value
        response.headers["X-Datacenter"] = settings.datacenter
        return response

    app.include_router(router)
    app.include_router(health)
    return app


app = create_app()
