from __future__ import annotations

from dataforge.job_store.base import JobStore
from dataforge.job_store.redis import RedisJobStore
from dataforge.settings import redis_jobstore_url


def get_job_store() -> JobStore:
    return RedisJobStore(redis_jobstore_url())
