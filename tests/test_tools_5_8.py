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
        if path == "/v1/escrow/youtube/UC_TEST_UID_123":
            return httpx.Response(
                200,
                json={
                    "identity": {
                        "platform": "youtube",
                        "platform_uid": "UC_TEST_UID_123",
                        "handle": "@mrbeast",
                        "display_name": "MrBeast",
                        "avatar_url": "https://example.com/avatar.png",
                    },
                    "balances": [
                        {"token": "SOL", "amount": "2.5", "claimable": True},
                        {"token": "CLAWTUBE", "amount": "1000", "claimable": True},
                    ],
                },
            )
        elif path == "/v1/escrow/youtube/UC_NOT_FOUND":
            return httpx.Response(
                404,
                json={"code": "ESCROW_NOT_FOUND", "message": "Escrow account not found"},
            )
        elif path == "/v1/claim/verify":
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "claim_status": "ready",
                    "wire_tx_base64": "AQAAAA==",
                    "attestation": "attestation_proof",
                },
            )
        elif path == "/v1/refund/tx":
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"wire_tx_base64": "AQAAAA=="},
            )

    transport = httpx.MockTransport(handler)
    mock_client = ClawTubeClient(base_url="http://testbackend", transport=transport)
    monkeypatch.setattr(server, "get_client", lambda: mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_escrow_balance():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "get_creator_escrow_balance",
            {"platform": "youtube", "platform_uid": "UC_TEST_UID_123"},
        )
        assert res.data["identity"]["platform_uid"] == "UC_TEST_UID_123"
        assert len(res.data["balances"]) == 2
        assert res.data["balances"][0]["token"] == "SOL"


@pytest.mark.asyncio
async def test_verify_creator_claim():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "verify_creator_claim",
            {
                "platform": "youtube",
                "platform_uid": "UC_TEST_UID_123",
                "payout_wallet": "Payout1111111111111111111111111111111111111",
                "auth_token": "oauth_token_xyz",
                "method": "upload",
            },
        )
        assert res.data["claim_status"] == "ready"
        assert res.data["wire_tx_base64"] == "AQAAAA=="
        assert res.data["attestation"] == "attestation_proof"


@pytest.mark.asyncio
async def test_refund_expired_tip():
    async with Client(server.mcp) as client:
        res = await client.call_tool(
            "refund_expired_tip",
            {"original_tip_reference": "ref_tip_999"},
        )
        assert res.data["wire_tx_base64"] == "AQAAAA=="


@pytest.mark.asyncio
async def test_error_mapping():
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "get_creator_escrow_balance",
                {"platform": "youtube", "platform_uid": "UC_NOT_FOUND"},
            )
        err_msg = str(exc_info.value)
        assert "ESCROW_NOT_FOUND" in err_msg or "Escrow account not found" in err_msg
        assert "ClawTube API error" in err_msg


@pytest.mark.asyncio
async def test_list_tools_returns_7():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        assert len(tools) == 7
        names = {t.name for t in tools}
        expected_names = {
            "resolve_creator",
            "estimate_tip_usd",
            "create_tip_tx",
            "verify_tip_status",
            "get_creator_escrow_balance",
            "verify_creator_claim",
            "refund_expired_tip",
        }
        assert names == expected_names
