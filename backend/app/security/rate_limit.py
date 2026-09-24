from fastapi import Request, Response
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter as _RateLimiter, WebSocketRateLimiter
from app.security.session import get_current_user_id


class RateLimiter(_RateLimiter):
    """Same as fastapi_limiter's RateLimiter, but without the route lookup.

    The original __call__ walks `request.app.routes` looking for a Route
    object with a matching `.path`, purely to build a key that disambiguates
    several RateLimiter instances stacked on the exact same route. On this
    project's FastAPI version, `app.include_router(...)` wraps every included
    router in an `_IncludedRouter` object that has no `.path` attribute, so
    that walk crashes with `AttributeError` on every single request — every
    rate-limited route 500s unconditionally.

    This app never stacks more than one RateLimiter per route, so that
    lookup buys nothing here. This override keys on the request's own path
    and method instead (always available on `request.scope`, no
    `app.routes` involved), which still keeps routes independent from each
    other — including two routes that share the same `identifier` function,
    like `user_identifier` below — without ever touching the broken code
    path.
    """

    async def __call__(self, request: Request, response: Response):
        rate_key = await self.identifier(request)
        key = f"{rate_key}:{request.scope['path']}:{request.method}"
        success = await self.limiter.try_acquire_async(key, blocking=self.blocking)
        if not success:
            return await self.callback(request, response)


async def user_identifier(request: Request) -> str:
    redis = request.app.state.redis
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    return str(user_id)


loginLimiter = RateLimiter(limiter=Limiter(Rate(10, Duration.MINUTE)))
registerLimiter = RateLimiter(limiter=Limiter(Rate(5, Duration.HOUR)))
forgotPasswordLimiter = RateLimiter(limiter=Limiter(Rate(3, Duration.HOUR)))
oauthLoginLimiter = RateLimiter(limiter=Limiter(Rate(10, Duration.MINUTE)))
LikeLimiter = RateLimiter(limiter=Limiter(Rate(20, Duration.MINUTE)), identifier=user_identifier)
blockLimiter = RateLimiter(limiter=Limiter(Rate(10, Duration.MINUTE)), identifier=user_identifier)
uploadPhotoLimiter = RateLimiter(limiter=Limiter(Rate(50, Duration.HOUR)), identifier=user_identifier)
messageLimiter = WebSocketRateLimiter(limiter=Limiter(Rate(1, Duration.SECOND)), identifier=user_identifier)
reportLimiter = RateLimiter(limiter=Limiter(Rate(5, Duration.HOUR)), identifier=user_identifier)
