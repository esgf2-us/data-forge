from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import redis

from dataforge.job_store.base import JobStore
from dataforge.models.job import (
    Job,
    JobPublication,
    JobResultMetadata,
    JobStatus,
    JobSubmission,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _encode_cursor(created_at_ms: int, job_id: str) -> str:
    raw = json.dumps({"t": int(created_at_ms), "id": job_id}).encode("utf-8")
    # Opaque cursor for clients.
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[int, str]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    return int(data["t"]), str(data["id"])


_SET_STATUS_LUA = """
local job_key = KEYS[1]
local z_old = KEYS[2]
local z_new = KEYS[3]

local job_id = ARGV[1]
local expected = ARGV[2]
local new = ARGV[3]
local now_ms = ARGV[4]

if redis.call('EXISTS', job_key) == 0 then
  return {err='not_found'}
end

local cur = redis.call('HGET', job_key, 'status')
if cur ~= expected then
  return {0, cur}
end

local allowed = 0
if cur == 'queued' and (new == 'running' or new == 'cancelled') then
  allowed = 1
elseif cur == 'running' and (new == 'completed' or new == 'failed' or new == 'cancelled') then
  allowed = 1
end
if allowed == 0 then
  return {err='transition_not_allowed'}
end

local created_at_ms = redis.call('HGET', job_key, 'created_at_ms')
if created_at_ms == false then
  created_at_ms = '0'
end

redis.call('HSET', job_key, 'status', new, 'updated_at_ms', now_ms)

if new == 'running' then
  local started = redis.call('HGET', job_key, 'started_at_ms')
  if started == false or started == '' then
    redis.call('HSET', job_key, 'started_at_ms', now_ms)
  end
end

if new == 'completed' or new == 'failed' or new == 'cancelled' then
  local completed = redis.call('HGET', job_key, 'completed_at_ms')
  if completed == false or completed == '' then
    redis.call('HSET', job_key, 'completed_at_ms', now_ms)
  end
end

redis.call('ZREM', z_old, job_id)
redis.call('ZADD', z_new, created_at_ms, job_id)

return {1, new}
"""


_CANCEL_LUA = """
local job_key = KEYS[1]
local z_queued = KEYS[2]
local z_running = KEYS[3]
local z_cancelled = KEYS[4]

local job_id = ARGV[1]
local now_ms = ARGV[2]

if redis.call('EXISTS', job_key) == 0 then
  return {err='not_found'}
end

local cur = redis.call('HGET', job_key, 'status')
if cur == 'completed' or cur == 'failed' or cur == 'cancelled' then
  return {0, cur}
end

if cur ~= 'queued' and cur ~= 'running' then
  return {err='transition_not_allowed'}
end

local created_at_ms = redis.call('HGET', job_key, 'created_at_ms')
if created_at_ms == false then
  created_at_ms = '0'
end

redis.call('HSET', job_key, 'status', 'cancelled', 'updated_at_ms', now_ms)

local completed = redis.call('HGET', job_key, 'completed_at_ms')
if completed == false or completed == '' then
  redis.call('HSET', job_key, 'completed_at_ms', now_ms)
end

if cur == 'queued' then
  redis.call('ZREM', z_queued, job_id)
else
  redis.call('ZREM', z_running, job_id)
end
redis.call('ZADD', z_cancelled, created_at_ms, job_id)

return {1, 'cancelled'}
"""


class RedisJobStore(JobStore):
    def __init__(self, redis_url: str) -> None:
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._set_status = self._r.register_script(_SET_STATUS_LUA)
        self._cancel = self._r.register_script(_CANCEL_LUA)

    def create(self, submission: JobSubmission) -> Job:
        job_id = f"job-{uuid4()}"

        now = _now()
        now_ms = _ms(now)

        job = Job(
            id=job_id,
            status=JobStatus.QUEUED,
            submission=submission,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            progress_total=None,
            progress_done=None,
            error_message=None,
            result_url=None,
            publication=None,
            result_metadata=None,
        )

        key = f"job:{job_id}"
        pipe = self._r.pipeline(transaction=True)
        pipe.hset(
            key,
            mapping={
                "id": job.id,
                "status": job.status.value,
                "created_at_ms": str(now_ms),
                "updated_at_ms": str(now_ms),
                "submission_json": submission.model_dump_json(),
            },
        )
        pipe.zadd("jobs:created", {job_id: now_ms})
        pipe.zadd(f"jobs:status:{job.status.value}", {job_id: now_ms})
        pipe.execute()
        return job

    def get(self, job_id: str) -> Job:
        data = self._r.hgetall(f"job:{job_id}")
        if not data:
            raise KeyError(job_id)
        return self._job_from_hash(data)

    def list(
        self, status: JobStatus | None, limit: int, cursor: str | None
    ) -> tuple[list[Job], str | None]:
        if limit <= 0:
            return [], None

        zkey = f"jobs:status:{status.value}" if status is not None else "jobs:created"

        cursor_t: tuple[int, str] | None = None
        max_score: int | str = "+inf"
        if cursor is not None:
            cursor_t = _decode_cursor(cursor)
            max_score = cursor_t[0]

        # We want deterministic ordering: (created_at_ms desc, job_id desc).
        # Redis zsets already do score desc then member desc for ZREVRANGE.
        want = limit + 1
        accepted: list[tuple[str, int]] = []
        offset = 0
        batch = max(50, want * 5)
        while len(accepted) < want:
            items = self._r.zrevrangebyscore(
                zkey,
                max=max_score,
                min="-inf",
                start=offset,
                num=batch,
                withscores=True,
            )
            if not items:
                break

            offset += len(items)
            for member, score in items:
                s = int(score)
                if cursor_t is not None:
                    ct, cid = cursor_t
                    if s > ct or (s == ct and member >= cid):
                        continue
                accepted.append((member, s))
                if len(accepted) >= want:
                    break

        page = accepted[:limit]
        if not page:
            return [], None

        job_ids = [jid for jid, _ in page]
        jobs = self._get_many(job_ids)

        next_cursor = None
        if len(accepted) > limit:
            last_id, last_score = page[-1]
            next_cursor = _encode_cursor(last_score, last_id)
        return jobs, next_cursor

    def set_status(self, job_id: str, expected: JobStatus, new: JobStatus) -> Job:
        try:
            res = self._set_status(
                keys=[
                    f"job:{job_id}",
                    f"jobs:status:{expected.value}",
                    f"jobs:status:{new.value}",
                ],
                args=[job_id, expected.value, new.value, str(_ms(_now()))],
            )
        except redis.ResponseError as e:
            msg = str(e)
            if "not_found" in msg:
                raise KeyError(job_id) from e
            if "transition_not_allowed" in msg:
                raise ValueError(
                    f"job {job_id} transition not allowed: {expected.value} -> {new.value}"
                ) from e
            raise

        # Lua returns: [1, new] on success, [0, cur] on mismatch, or error.
        if isinstance(res, list) and res and int(res[0]) == 1:
            return self.get(job_id)
        if isinstance(res, list) and res and int(res[0]) == 0:
            cur = str(res[1])
            raise ValueError(
                f"job {job_id} status mismatch: expected {expected.value}, got {cur}"
            )
        raise ValueError(
            f"job {job_id} transition not allowed: {expected.value} -> {new.value}"
        )

    def set_progress(self, job_id: str, done: int, total: int) -> Job:
        if self._r.exists(f"job:{job_id}") == 0:
            raise KeyError(job_id)
        now_ms = _ms(_now())
        self._r.hset(
            f"job:{job_id}",
            mapping={
                "progress_done": str(done),
                "progress_total": str(total),
                "updated_at_ms": str(now_ms),
            },
        )
        return self.get(job_id)

    def set_result(self, job_id: str, result_url: str) -> Job:
        if self._r.exists(f"job:{job_id}") == 0:
            raise KeyError(job_id)
        now_ms = _ms(_now())
        self._r.hset(
            f"job:{job_id}",
            mapping={"result_url": result_url, "updated_at_ms": str(now_ms)},
        )
        return self.get(job_id)

    def set_result_metadata(self, job_id: str, metadata: JobResultMetadata) -> Job:
        if self._r.exists(f"job:{job_id}") == 0:
            raise KeyError(job_id)
        now_ms = _ms(_now())
        self._r.hset(
            f"job:{job_id}",
            mapping={
                "result_metadata_json": metadata.model_dump_json(),
                "updated_at_ms": str(now_ms),
            },
        )
        return self.get(job_id)

    def set_error(self, job_id: str, error_message: str) -> Job:
        if self._r.exists(f"job:{job_id}") == 0:
            raise KeyError(job_id)
        now_ms = _ms(_now())
        self._r.hset(
            f"job:{job_id}",
            mapping={"error_message": error_message, "updated_at_ms": str(now_ms)},
        )
        return self.get(job_id)

    def set_publication(self, job_id: str, publication: JobPublication) -> Job:
        if self._r.exists(f"job:{job_id}") == 0:
            raise KeyError(job_id)
        now_ms = _ms(_now())
        self._r.hset(
            f"job:{job_id}",
            mapping={
                "publication_json": publication.model_dump_json(),
                "updated_at_ms": str(now_ms),
            },
        )
        return self.get(job_id)

    def cancel(self, job_id: str) -> Job:
        try:
            res = self._cancel(
                keys=[
                    f"job:{job_id}",
                    "jobs:status:queued",
                    "jobs:status:running",
                    "jobs:status:cancelled",
                ],
                args=[job_id, str(_ms(_now()))],
            )
        except redis.ResponseError as e:
            msg = str(e)
            if "not_found" in msg:
                raise KeyError(job_id) from e
            if "transition_not_allowed" in msg:
                raise ValueError(f"job {job_id} transition not allowed") from e
            raise

        # Lua returns: [1, 'cancelled'] if changed, [0, cur] if already terminal.
        if isinstance(res, list) and res and int(res[0]) in (0, 1):
            return self.get(job_id)
        raise ValueError(f"job {job_id} transition not allowed")

    def _get_many(self, job_ids: list[str]) -> list[Job]:
        pipe = self._r.pipeline(transaction=False)
        for jid in job_ids:
            pipe.hgetall(f"job:{jid}")
        rows = pipe.execute()

        out: list[Job] = []
        for jid, data in zip(job_ids, rows, strict=True):
            if not data:
                raise KeyError(jid)
            out.append(self._job_from_hash(data))
        return out

    def _job_from_hash(self, data: dict[str, str]) -> Job:
        sub = JobSubmission.model_validate_json(data["submission_json"])

        created_at_ms = int(data["created_at_ms"])
        updated_at_ms = int(data["updated_at_ms"])

        started_at_ms = data.get("started_at_ms")
        completed_at_ms = data.get("completed_at_ms")

        progress_total = data.get("progress_total")
        progress_done = data.get("progress_done")
        publication_json = data.get("publication_json")
        result_metadata_json = data.get("result_metadata_json")

        return Job(
            id=data["id"],
            status=JobStatus(data["status"]),
            submission=sub,
            created_at=_dt(created_at_ms),
            updated_at=_dt(updated_at_ms),
            started_at=_dt(int(started_at_ms)) if started_at_ms else None,
            completed_at=_dt(int(completed_at_ms)) if completed_at_ms else None,
            progress_total=int(progress_total) if progress_total else None,
            progress_done=int(progress_done) if progress_done else None,
            error_message=data.get("error_message") or None,
            result_url=data.get("result_url") or None,
            publication=(
                JobPublication.model_validate_json(publication_json)
                if publication_json
                else None
            ),
            result_metadata=(
                JobResultMetadata.model_validate_json(result_metadata_json)
                if result_metadata_json
                else None
            ),
        )
