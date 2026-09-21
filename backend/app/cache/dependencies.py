from fastapi import Request

def get_redis(request: Request):
    """Provide the shared Redis client (FastAPI dependency).

    Args:
        request: Incoming request, used to reach ``app.state``.

    Returns:
        The Redis client created in the application lifespan.
    """
    return request.app.state.redis