from __future__ import annotations

from importlib.metadata import version
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response

from dataforge.api.routes.jobs import router as jobs_router
from dataforge.models.config import InvalidConfigError, InvalidInputError
from dataforge.monitoring.metrics import API_REQUEST_LATENCY_SECONDS, metrics_payload
from dataforge.settings import api_keys, cors_allowed_origins, output_mode, stac_api


def create_app() -> FastAPI:
    app = FastAPI(
        title="Data-Forge API",
        version=version("data-forge"),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        started = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - started
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        API_REQUEST_LATENCY_SECONDS.labels(
            method=request.method, path=request.url.path
        ).observe(elapsed)
        return response

    @app.middleware("http")
    async def enforce_api_key(request: Request, call_next):
        expected = api_keys()
        if expected and request.url.path.startswith("/api/v1"):
            provided = request.headers.get("X-API-Key")
            if provided not in expected:
                return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    @app.exception_handler(InvalidInputError)
    async def invalid_input_handler(_: Request, exc: InvalidInputError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidConfigError)
    async def invalid_config_handler(_: Request, exc: InvalidConfigError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "version": version("data-forge"),
            "output_mode": output_mode(),
            "stac_configured": bool(stac_api()),
        }

    @app.get("/metrics", tags=["monitoring"])
    def metrics() -> Response:
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    app.include_router(jobs_router)
    return app
