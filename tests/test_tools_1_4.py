import json
import httpx
import pytest
from fastmcp import Client

import server
from client import ClawTubeClient


@pytest.fixture(autouse=True)
def mock_clawtube_backend(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/resolve":
            body = json.loads(request.content)
            if body.get("input") == "@error":
                return httpx.Response(
                    404,
                    json={"code": "NOT_FOUND", "message": "Creator handle @error not found"},
                )
            if body.get("input") == "@ratelimit":
                return httpx.Response(
                    429,
                    json={"code": "RATE_LIMITED", "message": "Rate limit exceeded: Maximum 20 creator lookups per minute."},
                )
            return httpx.Response(
                200,
                json={
                    "platform": body.get("platform", "youtube"),
                    "platform_uid": "UC_TEST_UID_123",
                    "handle": body.get("input", "@test"),
                    "display_name": "Test Creator",
                    "avatar_url": "https://example.com/avatar.png",
                },
            )
        elif path == "/v1/price":
            body = json.loads(request.content)
            amt = float(body.get("amount_usd", 1.0))
            return httpx.Response(
                200,
                json={
                    "token_amount": amt / 200.0,
                    "price_usd": 200.0,
                },
            )
        elif path == "/v1/tip/tx":
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "wire_tx_base64": "AQAAAA==",
                    "reference_id": "ref_mock_123",
                    "escrow_pda": "EscrowPDA111111111111111111111111111111111",
                },
            )
        elif path == "/v1/tip/status":
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "status": "finalized",
                    "signature": body.get("reference_id_or_signature", "sig_default"),
                },
            )
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handler)
    mock_client = ClawTubeClient(base_url="http://testbackend", transport=transport)
    monkeypatch.setattr(server, "get_client", lambda: mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_resolve_creator():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "resolve_creator", {"platform": "youtube", "input": "@mrbeast"}
        )
        assert res.data["platform_uid"] == "UC_TEST_UID_123"
        assert res.data["handle"] == "@mrbeast"
        assert res.data["display_name"] == "Test Creator"


@pytest.mark.asyncio
async def test_estimate_tip_usd():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "estimate_tip_usd", {"amount_usd": 50.0, "token_symbol": "SOL"}
        )
        assert res.data["token_amount"] == 0.25
        assert res.data["price_usd"] == 200.0


@pytest.mark.asyncio
async def test_create_tip_tx():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "create_tip_tx",
            {
                "platform": "youtube",
                "platform_uid": "UC_TEST_UID_123",
                "donor_wallet": "DonorW22222222222222222222222222222222",
                "token_symbol": "SOL",
                "amount": 1.5,
                "message": "Great video!",
                "donor_name": "Alice",
            },
        )
        assert res.data["wire_tx_base64"] == "AQAAAA=="
        assert res.data["reference_id"] == "ref_mock_123"
        assert res.data["escrow_pda"] == "EscrowPDA111111111111111111111111111111111"


@pytest.mark.asyncio
async def test_verify_tip_status():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "verify_tip_status", {"reference_id_or_signature": "sig_999"}
        )
        assert res.data["status"] == "finalized"
        assert res.data["signature"] == "sig_999"


@pytest.mark.asyncio
async def test_api_error_maps_to_runtimeerror():
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "resolve_creator", {"platform": "youtube", "input": "@error"}
            )
        err_msg = str(exc_info.value)
        assert "NOT_FOUND" in err_msg or "not found" in err_msg

@pytest.mark.asyncio
async def test_resolve_creator_rate_limited():
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "resolve_creator", {"platform": "youtube", "input": "@ratelimit"}
            )
        err_msg = str(exc_info.value)
        assert "RATE_LIMITED" in err_msg or "429" in err_msg
        assert "20 creator lookups per minute" in err_msg
        assert "ClawTube API error" in err_msg
