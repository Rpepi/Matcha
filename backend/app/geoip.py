"""Approximate location from an IP address.

Used when a user does not share their GPS position: the subject asks that they
are located anyway, without being asked. Two free services that need no key are
tried in turn (ip-api.com, then ipwho.is); anything going wrong with one of them
(network, timeout, odd answer) just moves on to the next, and when both fail the
user is simply not located.

A private address (the browser on the same machine, or the Vite proxy in Docker)
means nothing to these services: the lookup is then made without an address,
which locates the server's own public address, i.e. the network the user is on.
"""
import ipaddress
import math
import httpx
from fastapi import HTTPException, Request
from app.log import get_logger
from app.validation import clean_str, MAX_CITY

logger = get_logger(__name__)

TIMEOUT_SECONDS = 3.0


def client_ip(request: Request) -> str | None:
    """The address of the browser: the first ``X-Forwarded-For`` hop, else the peer.

    Only used to place the user on a map, never for anything security related,
    so a forged header only moves the forger.

    Args:
        request: Incoming request.

    Returns:
        The address as text, or None when unknown.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else None


def public_ip(ip: str | None) -> str | None:
    """Keep an address only if a geolocation service can know it.

    Args:
        ip: An address as text, possibly None or malformed.

    Returns:
        The normalised address, or None for a missing, malformed, private,
        loopback, link-local, reserved or unspecified one.
    """
    try:
        address = ipaddress.ip_address(ip or "")
    except ValueError:
        return None
    if not address.is_global:
        return None
    return str(address)


def _result(latitude, longitude, city, country) -> dict | None:
    """Turn a provider's answer into the app's shape, or None if it is unusable.

    The place name comes from a third party, so it goes through the same
    validation as a city typed by a user; a name that fails it is dropped,
    not the coordinates.
    """
    latitude, longitude = float(latitude), float(longitude)
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    label = ", ".join(part for part in (city, country) if isinstance(part, str) and part.strip())
    try:
        label = clean_str(label[:MAX_CITY], "city", MAX_CITY) if label else None
    except HTTPException:
        label = None
    return {"latitude": latitude, "longitude": longitude, "city": label}


async def _ip_api(client: httpx.AsyncClient, ip: str | None) -> dict | None:
    response = await client.get(f"http://ip-api.com/json/{ip or ''}", params={"fields": "status,lat,lon,city,country"})
    data = response.json()
    if data.get("status") != "success":
        return None
    return _result(data["lat"], data["lon"], data.get("city"), data.get("country"))


async def _ipwho(client: httpx.AsyncClient, ip: str | None) -> dict | None:
    response = await client.get(f"https://ipwho.is/{ip or ''}")
    data = response.json()
    if data.get("success") is not True:
        return None
    return _result(data["latitude"], data["longitude"], data.get("city"), data.get("country"))


PROVIDERS = (_ip_api, _ipwho)


async def locate(ip: str | None) -> dict | None:
    """Find roughly where an address is.

    Args:
        ip: The browser's address; a private or missing one locates the
            server's public address instead (see the module docstring).

    Returns:
        ``{"latitude": float, "longitude": float, "city": str | None}``, or
        None when no provider could answer.
    """
    target = public_ip(ip)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for provider in PROVIDERS:
            try:
                found = await provider(client, target)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                logger.warning("IP geolocation: %s failed", provider.__name__, exc_info=True)
                continue
            if found is not None:
                return found
    return None
