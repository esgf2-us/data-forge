from __future__ import annotations

from importlib.metadata import version
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import Response

from dataforge.api.routes.jobs import router as jobs_router
from dataforge.monitoring.metrics import API_REQUEST_LATENCY_SECONDS, metrics_payload
from dataforge.settings import cors_allowed_origins, output_mode, stac_api


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
