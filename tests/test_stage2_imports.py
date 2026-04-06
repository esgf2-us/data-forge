def test_stage2_deps_import() -> None:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import dramatiq  # noqa: F401
    from dramatiq.brokers.redis import RedisBroker  # noqa: F401
    import redis  # noqa: F401
    import uvicorn  # noqa: F401
