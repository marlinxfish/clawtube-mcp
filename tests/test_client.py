import json
import httpx
import pytest

from client import ClawTubeApiError, ClawTubeClient


@pytest.mark.asyncio
async def test_resolve_creator_sends_post():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/resolve"
        body = json.loads(request.content)
        assert body == {"platform": "youtube", "input": "@mrbeast"}
        return httpx.Response(
            200,
            json={
                "platform": "youtube",
                "platform_uid": "UCX6OQ3DkcsbYNE6H8uQQuVA",
                "handle": "@mrbeast",
                "display_name": "MrBeast",
                "avatar_url": "https://example.com/avatar.jpg",
            },
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.resolve_creator(platform="youtube", input="@mrbeast")
    assert res["platform_uid"] == "UCX6OQ3DkcsbYNE6H8uQQuVA"
    assert res["handle"] == "@mrbeast"
    await client.aclose()


@pytest.mark.asyncio
async def test_create_tip_tx_payload():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/tip/tx"
        body = json.loads(request.content)
        assert body == {
            "platform": "youtube",
            "platform_uid": "UCX6OQ3DkcsbYNE6H8uQQuVA",
            "donor_wallet": "DonorW22222222222222222222222222222222",
            "token_symbol": "SOL",
            "amount": 0.5,
            "message": "Keep it up!",
            "donor_name": "Alice",
        }
        return httpx.Response(
            200,
            json={
                "wire_tx_base64": "AQAAAA==",
                "reference_id": "ref_123",
                "escrow_pda": "EscrowPDA111111111111111111111111111111111",
            },
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.create_tip_tx(
        platform="youtube",
        platform_uid="UCX6OQ3DkcsbYNE6H8uQQuVA",
        donor_wallet="DonorW22222222222222222222222222222222",
        token_symbol="SOL",
        amount=0.5,
        message="Keep it up!",
        donor_name="Alice",
    )
    assert res["wire_tx_base64"] == "AQAAAA=="
    assert res["reference_id"] == "ref_123"
    await client.aclose()


@pytest.mark.asyncio
async def test_verify_claim_sends_method():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/claim/verify"
        body = json.loads(request.content)
        assert body == {
            "platform": "youtube",
            "platform_uid": "UCX6OQ3DkcsbYNE6H8uQQuVA",
            "payout_wallet": "PayoutW22222222222222222222222222222222",
            "auth_token": "secret_oauth_token",
            "method": "oauth",
        }
        return httpx.Response(
            200,
            json={
                "claim_status": "ready",
                "wire_tx_base64": "AQAAAA==",
                "attestation": "attestation_bytes",
            },
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.verify_creator_claim(
        platform="youtube",
        platform_uid="UCX6OQ3DkcsbYNE6H8uQQuVA",
        payout_wallet="PayoutW22222222222222222222222222222222",
        auth_token="secret_oauth_token",
        method="oauth",
    )
    assert res["claim_status"] == "ready"
    await client.aclose()


@pytest.mark.asyncio
async def test_tip_status():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/tip/status"
        body = json.loads(request.content)
        assert body == {"reference_id_or_signature": "sig_abc123"}
        return httpx.Response(
            200,
            json={
                "status": "finalized",
                "signature": "sig_abc123",
            },
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.verify_tip_status(reference_id_or_signature="sig_abc123")
    assert res["status"] == "finalized"
    assert res["signature"] == "sig_abc123"
    await client.aclose()


@pytest.mark.asyncio
async def test_escrow_balance_get():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/escrow/youtube/UCX6OQ3DkcsbYNE6H8uQQuVA"
        return httpx.Response(
            200,
            json={
                "identity": {
                    "platform": "youtube",
                    "platform_uid": "UCX6OQ3DkcsbYNE6H8uQQuVA",
                    "handle": "@mrbeast",
                    "display_name": "MrBeast",
                    "avatar_url": "https://example.com/avatar.jpg",
                },
                "balances": [{"token": "SOL", "amount": "1.5", "claimable": True}],
            },
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.get_creator_escrow_balance(
        platform="youtube", platform_uid="UCX6OQ3DkcsbYNE6H8uQQuVA"
    )
    assert len(res["balances"]) == 1
    assert res["balances"][0]["token"] == "SOL"
    await client.aclose()


@pytest.mark.asyncio
async def test_refund_tx():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/refund/tx"
        body = json.loads(request.content)
        assert body == {"original_tip_reference": "ref_tip_456"}
        return httpx.Response(
            200,
            json={"wire_tx_base64": "AQAAAA=="},
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.refund_expired_tip(original_tip_reference="ref_tip_456")
    assert res["wire_tx_base64"] == "AQAAAA=="
    await client.aclose()


@pytest.mark.asyncio
async def test_sweep_tx():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/sweep/tx"
        body = json.loads(request.content)
        assert body == {
            "platform": "youtube",
            "platform_uid": "UCX6OQ3DkcsbYNE6H8uQQuVA",
            "dry_run": True,
            "sweeper_wallet": "Sweeper1111111111111111111111111111111111",
        }
        return httpx.Response(
            200,
            json={"wire_tx_base64": "AQAAAA==", "swept_entries_count": 3},
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.sweep_expired_escrow(
        platform="youtube",
        platform_uid="UCX6OQ3DkcsbYNE6H8uQQuVA",
        dry_run=True,
        sweeper_wallet="Sweeper1111111111111111111111111111111111",
    )
    assert res["swept_entries_count"] == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_price():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/price"
        body = json.loads(request.content)
        assert body == {"amount_usd": 10.0, "token_symbol": "SOL"}
        return httpx.Response(
            200,
            json={"token_amount": 0.05, "price_usd": 200.0},
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    res = await client.estimate_tip_usd(amount_usd=10.0, token_symbol="SOL")
    assert res["token_amount"] == 0.05
    assert res["price_usd"] == 200.0
    await client.aclose()


@pytest.mark.asyncio
async def test_api_error_raised():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"code": "INVALID_PARAM", "message": "Handle format is invalid"},
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    with pytest.raises(ClawTubeApiError) as exc_info:
        await client.resolve_creator("youtube", "bad-handle")

    err = exc_info.value
    assert err.status == 400
    assert err.code == "INVALID_PARAM"
    assert "Handle format is invalid" in err.message
    await client.aclose()

@pytest.mark.asyncio
async def test_rate_limited_429_raised():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"code": "RATE_LIMITED", "message": "Rate limit exceeded: Maximum 20 creator lookups per minute."},
        )

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(base_url="http://testserver", transport=transport)
    with pytest.raises(ClawTubeApiError) as exc_info:
        await client.resolve_creator("youtube", "@spam")

    err = exc_info.value
    assert err.status == 429
    assert err.code == "RATE_LIMITED"
    assert "20 creator lookups per minute" in err.message
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_on_5xx():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, json={"message": "Internal Server Error"})
        return httpx.Response(200, json={"status": "finalized", "signature": "sig123"})

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(
        base_url="http://testserver", transport=transport, backoff_factor=0.001
    )
    res = await client.verify_tip_status("sig123")
    assert res["status"] == "finalized"
    assert call_count == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_exhausted():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, json={"code": "SERVICE_UNAVAILABLE", "message": "Unavailable"})

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(
        base_url="http://testserver", transport=transport, backoff_factor=0.001
    )
    with pytest.raises(ClawTubeApiError) as exc_info:
        await client.verify_tip_status("sig123")

    assert exc_info.value.status == 503
    assert call_count == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_on_network_error():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection refused", request=request)
        return httpx.Response(200, json={"status": "finalized", "signature": "sig123"})

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(
        base_url="http://testserver", transport=transport, backoff_factor=0.001
    )
    res = await client.verify_tip_status("sig123")
    assert res["status"] == "finalized"
    assert call_count == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_no_retry_on_4xx():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "Creator not found"})

    transport = httpx.MockTransport(handler)
    client = ClawTubeClient(
        base_url="http://testserver", transport=transport, backoff_factor=0.001
    )
    with pytest.raises(ClawTubeApiError) as exc_info:
        await client.resolve_creator("youtube", "@nonexistent")

    assert exc_info.value.status == 404
    assert call_count == 1
    await client.aclose()
