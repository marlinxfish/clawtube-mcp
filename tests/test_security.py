"""Security and hardening test suite for ClawTube MCP Gateway.

Tests cover:
1. Wallet Address Validation (Base58 Solana public keys, length 32-44)
2. String Length & Injection Boundaries (null-byte rejection, field length caps)
3. Numeric Constraints (strictly positive, finite, max bound <= 100_000_000_000)
4. Error Sanitization & Information Leakage Prevention
5. Base URL / SSRF Protection (strict http/https validation)
6. Zero Private Key Exposure
7. Skills Provider Security (directory validation & path traversal prevention)
"""

import math
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client
from pydantic import ValidationError

import server
from client import ClawTubeApiError, ClawTubeClient
from exceptions import BackendConnectionError, InvalidInputError
from models import (
    CreateTipTxInput,
    EscrowBalanceInput,
    EstimateTipInput,
    RefundInput,
    ResolveInput,
    SweepInput,
    TipStatusInput,
    VerifyClaimInput,
)

VALID_SOLANA_WALLETS = [
    "11111111111111111111111111111111",  # 32 chars Base58
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # 43 chars Base58
    "So11111111111111111111111111111111111111112",  # 43 chars Base58
    "DonorW22222222222222222222222222222222",  # 38 chars Base58
]

INVALID_WALLETS = [
    "too_short",  # < 32 chars
    "11111111111111111111111111111111111111111111111111111111",  # > 44 chars
    "00000000000000000000000000000000",  # contains '0' (not in Base58)
    "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO",  # contains 'O' (not in Base58)
    "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",  # contains 'I' (not in Base58)
    "llllllllllllllllllllllllllllllll",  # contains 'l' (not in Base58)
    "So11111111111111111111111111111111111111112!",  # special char
    "So11111111 11111111111111111111111111111112",  # space
    "So11111111\x00111111111111111111111111111111112",  # null-byte
    "'; DROP TABLE users; -- 111111111111111111111",  # SQL injection
    "<script>alert(1)</script>11111111111111111111",  # XSS payload
]


# =============================================================================
# 1. Wallet Address Validation Tests
# =============================================================================


@pytest.mark.parametrize("wallet", VALID_SOLANA_WALLETS)
def test_donor_wallet_accepts_valid_base58(wallet: str):
    inp = CreateTipTxInput(
        platform="youtube",
        platform_uid="UC_VALID_123",
        donor_wallet=wallet,
        amount=1.0,
    )
    assert inp.donor_wallet == wallet


@pytest.mark.parametrize("wallet", INVALID_WALLETS)
def test_donor_wallet_rejects_invalid(wallet: str):
    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_VALID_123",
            donor_wallet=wallet,
            amount=1.0,
        )


@pytest.mark.parametrize("wallet", VALID_SOLANA_WALLETS)
def test_payout_wallet_accepts_valid_base58(wallet: str):
    inp = VerifyClaimInput(
        platform="youtube",
        platform_uid="UC_VALID_123",
        payout_wallet=wallet,
        auth_token="valid_token",
    )
    assert inp.payout_wallet == wallet


@pytest.mark.parametrize("wallet", INVALID_WALLETS)
def test_payout_wallet_rejects_invalid(wallet: str):
    with pytest.raises(ValidationError):
        VerifyClaimInput(
            platform="youtube",
            platform_uid="UC_VALID_123",
            payout_wallet=wallet,
            auth_token="valid_token",
        )


def test_sweeper_wallet_optional_and_validation():
    # Empty sweeper wallet is valid (optional)
    sweep_empty = SweepInput(sweeper_wallet="")
    assert sweep_empty.sweeper_wallet == ""

    # Valid Base58 sweeper wallet is valid
    sweep_valid = SweepInput(sweeper_wallet=VALID_SOLANA_WALLETS[0])
    assert sweep_valid.sweeper_wallet == VALID_SOLANA_WALLETS[0]

    # Invalid Base58 sweeper wallet is rejected
    for invalid_wallet in INVALID_WALLETS:
        with pytest.raises(ValidationError):
            SweepInput(sweeper_wallet=invalid_wallet)


# =============================================================================
# 2. String Length & Injection Boundaries Tests
# =============================================================================


def test_resolve_input_boundaries():
    # Valid input <= 128 chars
    valid = ResolveInput(input="a" * 128)
    assert len(valid.input) == 128

    # Over 128 chars rejected
    with pytest.raises(ValidationError):
        ResolveInput(input="a" * 129)

    # Empty or whitespace only rejected
    with pytest.raises(ValidationError):
        ResolveInput(input="")

    # Null-byte injection rejected
    with pytest.raises(ValidationError):
        ResolveInput(input="@mrbeast\x00extra")


def test_platform_uid_boundaries():
    # Valid platform_uid <= 64 chars
    valid = EscrowBalanceInput(platform_uid="UC_" + "a" * 60)
    assert len(valid.platform_uid) == 63

    # Over 64 chars rejected
    with pytest.raises(ValidationError):
        EscrowBalanceInput(platform_uid="a" * 65)

    # Null byte rejected
    with pytest.raises(ValidationError):
        EscrowBalanceInput(platform_uid="UC_123\x00")


def test_message_and_donor_name_boundaries():
    # Message max 280 chars
    valid_tx = CreateTipTxInput(
        platform="youtube",
        platform_uid="UC_VALID",
        donor_wallet=VALID_SOLANA_WALLETS[0],
        amount=1.0,
        message="m" * 280,
        donor_name="d" * 64,
    )
    assert len(valid_tx.message) == 280
    assert len(valid_tx.donor_name) == 64

    # Message > 280 rejected
    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_VALID",
            donor_wallet=VALID_SOLANA_WALLETS[0],
            amount=1.0,
            message="m" * 281,
        )

    # Donor name > 64 rejected
    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_VALID",
            donor_wallet=VALID_SOLANA_WALLETS[0],
            amount=1.0,
            donor_name="d" * 65,
        )

    # Null byte in message rejected
    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_VALID",
            donor_wallet=VALID_SOLANA_WALLETS[0],
            amount=1.0,
            message="hello\x00world",
        )


def test_reference_id_boundaries():
    # Valid reference <= 128 chars
    valid = TipStatusInput(reference_id_or_signature="sig_" + "a" * 120)
    assert len(valid.reference_id_or_signature) == 124

    # Over 128 chars rejected
    with pytest.raises(ValidationError):
        TipStatusInput(reference_id_or_signature="a" * 129)

    # Null byte rejected
    with pytest.raises(ValidationError):
        TipStatusInput(reference_id_or_signature="sig_123\x00")

    # Refund input reference <= 128 chars and rejects null byte
    valid_ref = RefundInput(original_tip_reference="ref_" + "a" * 120)
    assert len(valid_ref.original_tip_reference) == 124

    with pytest.raises(ValidationError):
        RefundInput(original_tip_reference="a" * 129)

    with pytest.raises(ValidationError):
        RefundInput(original_tip_reference="ref_123\x00")


def test_all_models_reject_null_bytes():
    # VerifyClaimInput
    with pytest.raises(ValidationError):
        VerifyClaimInput(
            platform_uid="UC_123\x00",
            payout_wallet=VALID_SOLANA_WALLETS[0],
            auth_token="valid_token",
        )
    with pytest.raises(ValidationError):
        VerifyClaimInput(
            platform_uid="UC_123",
            payout_wallet=VALID_SOLANA_WALLETS[0],
            auth_token="token\x00malicious",
        )

    # EstimateTipInput token_symbol
    with pytest.raises(ValidationError):
        EstimateTipInput(amount_usd=10.0, token_symbol="SOL\x00")


# =============================================================================
# 3. Numeric Constraints Tests
# =============================================================================


@pytest.mark.parametrize(
    "invalid_amt",
    [
        0.0,
        -1.0,
        -0.0001,
        float("nan"),
        float("inf"),
        float("-inf"),
        100_000_000_001.0,  # exceeds max bound
    ],
)
def test_estimate_tip_amount_usd_numeric_bounds(invalid_amt: float):
    with pytest.raises(ValidationError):
        EstimateTipInput(amount_usd=invalid_amt)


@pytest.mark.parametrize(
    "invalid_amt",
    [
        0.0,
        -1.0,
        -0.0001,
        float("nan"),
        float("inf"),
        float("-inf"),
        100_000_000_001.0,  # exceeds max bound
    ],
)
def test_create_tip_amount_numeric_bounds(invalid_amt: float):
    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_VALID",
            donor_wallet=VALID_SOLANA_WALLETS[0],
            amount=invalid_amt,
        )


@pytest.mark.parametrize("valid_amt", [0.000001, 1.0, 100.5, 100_000_000_000.0])
def test_valid_numeric_amounts_accepted(valid_amt: float):
    est = EstimateTipInput(amount_usd=valid_amt)
    assert est.amount_usd == valid_amt

    tx = CreateTipTxInput(
        platform="youtube",
        platform_uid="UC_VALID",
        donor_wallet=VALID_SOLANA_WALLETS[0],
        amount=valid_amt,
    )
    assert tx.amount == valid_amt


# =============================================================================
# 4. Error Sanitization & Information Leakage Prevention Tests
# =============================================================================


@pytest.mark.asyncio
async def test_network_error_sanitization_no_leak():
    """Ensure transport/connect errors do not leak internal socket details or raw tracebacks."""
    async def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "[Errno 111] Connect call failed ('127.0.0.1', 8080)", request=request
        )

    transport = httpx.MockTransport(failing_handler)
    client = ClawTubeClient(
        base_url="http://testbackend", transport=transport, backoff_factor=0.0001
    )

    with pytest.raises(ClawTubeApiError) as exc_info:
        await client.resolve_creator("youtube", "@mrbeast")

    err = exc_info.value
    assert err.code == "NETWORK_ERROR"
    # Ensure internal socket error strings and IP addresses are not leaked
    assert "Errno 111" not in err.message
    assert "127.0.0.1" not in err.message
    assert "Connect call failed" not in err.message
    assert "ClawTube backend is currently unreachable" in err.message
    await client.aclose()


@pytest.mark.asyncio
async def test_tool_error_sanitization():
    """Verify tool wrapper in server.py returns clean error without traceback leaks."""
    async def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("raw internal exception details", request=request)

    transport = httpx.MockTransport(failing_handler)
    mock_client = ClawTubeClient(
        base_url="http://testbackend", transport=transport, backoff_factor=0.0001
    )

    # Swap client
    original_client = server._client
    server._client = mock_client
    try:
        async with Client(server.mcp) as client:
            with pytest.raises(Exception) as exc_info:
                await client.call_tool(
                    "resolve_creator", {"platform": "youtube", "input": "@mrbeast"}
                )
            msg = str(exc_info.value)
            assert "raw internal exception details" not in msg
            assert "Traceback" not in msg
    finally:
        server._client = original_client
        await mock_client.aclose()


# =============================================================================
# 5. Base URL / SSRF Protection Tests
# =============================================================================


@pytest.mark.parametrize(
    "dangerous_url",
    [
        "file:///etc/passwd",
        "ftp://internal.vault.local",
        "gopher://127.0.0.1:70",
        "javascript:alert(1)",
        "data:text/plain;base64,SGVsbG8=",
        "ws://localhost:8080",
        "http://",  # missing host
        "https://",  # missing host
        "://invalid-uri",
    ],
)
def test_client_rejects_dangerous_base_urls(dangerous_url: str):
    with pytest.raises((ValueError, InvalidInputError)):
        ClawTubeClient(base_url=dangerous_url)


@pytest.mark.parametrize(
    "valid_url",
    [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://api.clawtube.xyz",
        "https://api.clawtube.xyz:8443/api",
    ],
)
def test_client_accepts_valid_base_urls(valid_url: str):
    client = ClawTubeClient(base_url=valid_url)
    assert str(client._http.base_url).rstrip("/").startswith(valid_url.rstrip("/"))


# =============================================================================
# 6. Zero Private Key Exposure Tests
# =============================================================================


def test_no_private_keys_in_models():
    """Verify none of the pydantic models declare private key or secret seed fields."""
    forbidden_terms = [
        "private_key",
        "secret_key",
        "privkey",
        "secret_seed",
        "mnemonic",
        "seed_phrase",
        "keypair",
    ]

    models = [
        ResolveInput,
        EstimateTipInput,
        CreateTipTxInput,
        TipStatusInput,
        EscrowBalanceInput,
        VerifyClaimInput,
        RefundInput,
        SweepInput,
    ]

    for model in models:
        field_names = set(model.model_fields.keys())
        for term in forbidden_terms:
            assert term not in field_names, f"Model {model.__name__} contains forbidden field {term}"


@pytest.mark.asyncio
async def test_no_private_keys_in_tool_schemas():
    """Verify none of the 8 MCP tools accept private keys as parameters."""
    forbidden_terms = [
        "private_key",
        "secret_key",
        "privkey",
        "secret_seed",
        "mnemonic",
        "seed_phrase",
        "keypair",
    ]

    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        for tool in tools:
            schema = tool.parameters if hasattr(tool, "parameters") else {}
            properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
            for prop in properties:
                for term in forbidden_terms:
                    assert term not in prop.lower(), f"Tool {tool.name} has parameter {prop} matching forbidden {term}"


# =============================================================================
# 7. Skills Provider Security Tests
# =============================================================================


def test_skills_root_verification_and_traversal_protection():
    """Verify skills directory resolution does not expose root or parent directories."""
    # Ensure SKILLS_ROOT resolves to a valid clawtube-skills directory or handles absence gracefully
    skills_root = server.SKILLS_ROOT
    assert not str(skills_root).endswith("..")
    # Verify SKILLS_ROOT does not expose filesystem root or parent repository root
    assert skills_root.name == "clawtube-skills"


@pytest.mark.asyncio
async def test_tool_rejects_invalid_wallet_e2e():
    """Verify FastMCP tool rejects invalid wallet address end-to-end."""
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "create_tip_tx",
                {
                    "platform": "youtube",
                    "platform_uid": "UC_VALID",
                    "donor_wallet": "invalid_short_wallet",
                    "amount": 1.0,
                },
            )
        assert "validation error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tool_rejects_invalid_amount_e2e():
    """Verify FastMCP tool rejects non-positive or oversized amount end-to-end."""
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("estimate_tip_usd", {"amount_usd": -10.0})
        assert "validation error" in str(exc_info.value).lower()

        with pytest.raises(Exception) as exc_info:
            await client.call_tool("estimate_tip_usd", {"amount_usd": 200_000_000_000.0})
        assert "validation error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tool_rejects_null_byte_e2e():
    """Verify FastMCP tool rejects null-byte injection end-to-end."""
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("resolve_creator", {"platform": "youtube", "input": "@mrbeast\x00extra"})
        assert "null-byte injection" in str(exc_info.value).lower() or "validation error" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_skills_provider_no_parent_directory_leak():
    """Verify skills provider only exposes clawtube-skills and not parent repository files."""
    async with Client(server.mcp) as client:
        resources = await client.list_resources()
        for r in resources:
            uri_str = str(r.uri)
            assert "clawtube-skills" in uri_str or uri_str.startswith("skill://clawtube")
            assert not uri_str.startswith("file:///")
            assert "clawtube-program" not in uri_str
            assert "clawtube-mcp" not in uri_str
