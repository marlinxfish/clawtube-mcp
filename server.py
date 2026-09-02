"""ClawTube Protocol MCP Gateway (FastMCP v3.4.7).

8 typed tools for AI Agents to interact with ClawTube Protocol on Solana.
Provides creator identity resolution, tip transaction assembly, on-chain confirmation,
escrow queries, dual-signature creator claims, expired tip refunds, and sweeper bounties.
"""

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.providers.skills import SkillProvider

from client import ClawTubeApiError, ClawTubeClient
from models import (
    CreateTipTxInput,
    EscrowBalanceInput,
    EstimateTipInput,
    Platform,
    RefundInput,
    ResolveInput,
    SweepInput,
    TipStatusInput,
    VerifyClaimInput,
)

mcp = FastMCP("ClawTube MCP")

# Register skills provider for AI agent operational guidance with safe resolution
SKILLS_ROOT = (Path(__file__).resolve().parent.parent / "clawtube-skills").resolve()
if SKILLS_ROOT.is_dir() and (SKILLS_ROOT / "SKILL.md").exists():
    mcp.add_provider(SkillProvider(skill_path=SKILLS_ROOT))

_client: ClawTubeClient | None = None


def get_client() -> ClawTubeClient:
    """Return singleton ClawTubeClient instance or default."""
    global _client
    if _client is None:
        _client = ClawTubeClient()
    return _client


# --- 8 Protocol Tools ---


@mcp.tool
async def resolve_creator(platform: Platform = "youtube", input: str = "") -> dict[str, Any]:
    """Resolve creator handle, username, or channel URL to immutable CreatorIdentity.

    Args:
        platform: Target social platform (e.g. 'youtube', 'x', 'instagram'). Default is 'youtube'.
        input: Creator handle (e.g. '@MrBeast'), username, or profile/channel URL (max 128 chars).

    Returns:
        CreatorIdentity dict with platform, platform_uid, handle, display_name, avatar_url.
    """
    params = ResolveInput(platform=platform, input=input)
    client = get_client()
    try:
        return await client.resolve_creator(platform=params.platform, input=params.input)
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def estimate_tip_usd(amount_usd: float = 1.0, token_symbol: str = "SOL") -> dict[str, Any]:
    """Estimate token quantity required for a target USD donation amount.

    Args:
        amount_usd: Target donation amount in USD (must be > 0 and <= 100,000,000,000).
        token_symbol: Token symbol to tip (e.g. 'SOL', '$CLAWTUBE', '$CLAW'). Default is 'SOL'.

    Returns:
        Price estimate dict with token_amount, price_usd, and symbol info.
    """
    params = EstimateTipInput(amount_usd=amount_usd, token_symbol=token_symbol)
    client = get_client()
    try:
        return await client.estimate_tip_usd(
            amount_usd=params.amount_usd, token_symbol=params.token_symbol
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def create_tip_tx(
    platform: Platform = "youtube",
    platform_uid: str = "",
    donor_wallet: str = "",
    token_symbol: str = "SOL",
    amount: float = 0.0,
    message: str = "",
    donor_name: str = "",
) -> dict[str, Any]:
    """Assemble an unsigned Solana Pay wire transaction for tipping a creator.

    The returned base64 wire transaction must be signed locally by the donor wallet.

    Args:
        platform: Target social platform (e.g. 'youtube'). Default is 'youtube'.
        platform_uid: Immutable creator platform UID (from resolve_creator, max 64 chars).
        donor_wallet: Base58 Solana public key of the donor (32-44 characters).
        token_symbol: Token to tip ('SOL', '$CLAWTUBE', '$CLAW'). Default is 'SOL'.
        amount: Token amount to donate (> 0 and <= 100,000,000,000).
        message: Optional memo or public message attached to the tip (max 280 chars).
        donor_name: Optional display name for the donor (max 64 chars).

    Returns:
        Dict with wire_tx_base64, reference_id, and escrow_pda.
    """
    params = CreateTipTxInput(
        platform=platform,
        platform_uid=platform_uid,
        donor_wallet=donor_wallet,
        token_symbol=token_symbol,
        amount=amount,
        message=message,
        donor_name=donor_name,
    )
    client = get_client()
    try:
        return await client.create_tip_tx(
            platform=params.platform,
            platform_uid=params.platform_uid,
            donor_wallet=params.donor_wallet,
            token_symbol=params.token_symbol,
            amount=params.amount,
            message=params.message,
            donor_name=params.donor_name,
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def verify_tip_status(reference_id_or_signature: str = "") -> dict[str, Any]:
    """Check on-chain confirmation status of a tip transaction.

    Args:
        reference_id_or_signature: Solana transaction signature or tip reference ID (max 128 chars).

    Returns:
        Dict with status ('finalized' | 'pending') and signature.
    """
    params = TipStatusInput(reference_id_or_signature=reference_id_or_signature)
    client = get_client()
    try:
        return await client.verify_tip_status(
            reference_id_or_signature=params.reference_id_or_signature
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def get_creator_escrow_balance(
    platform: Platform = "youtube", platform_uid: str = ""
) -> dict[str, Any]:
    """Query on-chain escrow PDA balances and claimable tokens for a creator.

    Args:
        platform: Target social platform. Default is 'youtube'.
        platform_uid: Immutable creator platform UID (max 64 chars).

    Returns:
        Dict with identity and list of balances per token.
    """
    params = EscrowBalanceInput(platform=platform, platform_uid=platform_uid)
    client = get_client()
    try:
        return await client.get_creator_escrow_balance(
            platform=params.platform, platform_uid=params.platform_uid
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def verify_creator_claim(
    platform: Platform = "youtube",
    platform_uid: str = "",
    payout_wallet: str = "",
    auth_token: str = "",
    method: str = "upload",
) -> dict[str, Any]:
    """Validate creator channel ownership and assemble dual-signature claim wire transaction.

    Args:
        platform: Target social platform. Default is 'youtube'.
        platform_uid: Immutable creator platform UID (max 64 chars).
        payout_wallet: Solana wallet public key where creator receives escrowed funds (32-44 characters Base58).
        auth_token: Verification credential (OAuth access token or verification code, max 512 chars).
        method: Verification method ('upload', 'oauth', or 'bio'). Default is 'upload'.

    Returns:
        Dict with claim_status, wire_tx_base64 (requiring Oracle + Creator signatures), attestation.
    """
    params = VerifyClaimInput(
        platform=platform,
        platform_uid=platform_uid,
        payout_wallet=payout_wallet,
        auth_token=auth_token,
        method=method,
    )
    client = get_client()
    try:
        return await client.verify_creator_claim(
            platform=params.platform,
            platform_uid=params.platform_uid,
            payout_wallet=params.payout_wallet,
            auth_token=params.auth_token,
            method=params.method,
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def refund_expired_tip(original_tip_reference: str = "") -> dict[str, Any]:
    """Assemble a refund wire transaction for an unclaimed tip in the refund window (days 91-120).

    Args:
        original_tip_reference: Original tip reference ID or escrow entry PDA address (max 128 chars).

    Returns:
        Dict with wire_tx_base64 for donor refund.
    """
    params = RefundInput(original_tip_reference=original_tip_reference)
    client = get_client()
    try:
        return await client.refund_expired_tip(
            original_tip_reference=params.original_tip_reference
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


@mcp.tool
async def sweep_expired_escrow(
    platform: Platform = "youtube",
    platform_uid: str = "",
    dry_run: bool = True,
    sweeper_wallet: str = "",
) -> dict[str, Any]:
    """Assemble a batch sweep transaction to sweep expired donations (>120 days) to treasury.

    Supports dry-run mode for discovering eligible entries before broadcasting.

    Args:
        platform: Target social platform. Default is 'youtube'.
        platform_uid: Optional creator platform UID (leave empty for platform-wide sweep, max 64 chars).
        dry_run: If True, simulates sweep without committing (default: True).
        sweeper_wallet: Solana wallet public key of sweeper claiming the bounty reward (optional, 32-44 chars Base58).

    Returns:
        Dict with wire_tx_base64 and swept_entries_count.
    """
    params = SweepInput(
        platform=platform,
        platform_uid=platform_uid,
        dry_run=dry_run,
        sweeper_wallet=sweeper_wallet,
    )
    client = get_client()
    try:
        return await client.sweep_expired_escrow(
            platform=params.platform,
            platform_uid=params.platform_uid,
            dry_run=params.dry_run,
            sweeper_wallet=params.sweeper_wallet,
        )
    except ClawTubeApiError as e:
        raise RuntimeError(f"ClawTube API error ({e.code or e.status}): {e.message}") from e


if __name__ == "__main__":
    mcp.run()
