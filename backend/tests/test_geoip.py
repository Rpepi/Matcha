from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from app import geoip
from app.geoip import public_ip, client_ip, locate


class TestPublicIp:
    @pytest.mark.parametrize("ip", ["127.0.0.1", "172.18.0.5", "10.0.0.1", "192.168.1.2", "::1", "fe80::1", "", None, "nope", "0.0.0.0"])
    def test_addresses_a_service_cannot_know_are_dropped(self, ip):
        assert public_ip(ip) is None

    @pytest.mark.parametrize("ip", ["161.246.157.34", "8.8.8.8", "2001:4860:4860::8888"])
    def test_public_addresses_are_kept(self, ip):
        assert public_ip(ip) == ip


class TestClientIp:
    def test_first_forwarded_hop_wins(self):
        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.7, 172.18.0.3"}
        assert client_ip(request) == "203.0.113.7"

    def test_falls_back_to_the_peer(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "172.18.0.3"
        assert client_ip(request) == "172.18.0.3"


def answer(json_data):
    response = MagicMock()
    response.json = MagicMock(return_value=json_data)
    return response


def patched_client(*responses):
    client = AsyncMock()
    client.get = AsyncMock(side_effect=list(responses))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    return patch("app.geoip.httpx.AsyncClient", return_value=context), client


class TestLocate:
    async def test_first_provider_answers(self):
        patcher, client = patched_client(answer({"status": "success", "lat": 13.7, "lon": 100.5, "city": "Bangkok", "country": "Thailand"}))
        with patcher:
            found = await locate("8.8.8.8")
        assert found == {"latitude": 13.7, "longitude": 100.5, "city": "Bangkok, Thailand"}
        assert "8.8.8.8" in client.get.call_args.args[0]

    async def test_private_address_asks_for_the_servers_own_location(self):
        patcher, client = patched_client(answer({"status": "success", "lat": 1, "lon": 2, "city": None, "country": None}))
        with patcher:
            found = await locate("172.18.0.3")
        assert client.get.call_args.args[0] == "http://ip-api.com/json/"
        assert found["city"] is None

    async def test_falls_back_to_the_second_provider(self):
        patcher, _ = patched_client(
            httpx.ConnectTimeout("slow"),
            answer({"success": True, "latitude": 18.79, "longitude": 98.98, "city": "Chiang Mai", "country": "Thailand"}),
        )
        with patcher:
            found = await locate(None)
        assert found == {"latitude": 18.79, "longitude": 98.98, "city": "Chiang Mai, Thailand"}

    async def test_both_failing_is_none(self):
        patcher, _ = patched_client(answer({"status": "fail"}), answer({"success": False}))
        with patcher:
            assert await locate(None) is None

    @pytest.mark.parametrize("data", [
        {"status": "success", "lat": 91, "lon": 0},
        {"status": "success", "lat": "nan", "lon": 0},
        {"status": "success", "lat": "x", "lon": 0},
        {"status": "success"},
    ])
    async def test_absurd_coordinates_are_ignored(self, data):
        patcher, _ = patched_client(answer(data), answer({"success": False}))
        with patcher:
            assert await locate(None) is None

    async def test_a_hostile_place_name_is_dropped_but_not_the_position(self):
        patcher, _ = patched_client(answer({"status": "success", "lat": 1, "lon": 2, "city": "Bad\x00City", "country": None}))
        with patcher:
            found = await locate(None)
        assert found == {"latitude": 1.0, "longitude": 2.0, "city": None}
