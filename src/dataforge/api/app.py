from __future__ import annotations

from fastapi import FastAPI

from dataforge.api.routes.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(jobs_router)
    return app
