"""Data models for ClawTube MCP Gateway with strict security validation."""

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Platform = Literal["youtube", "x", "instagram", "threads", "tiktok", "facebook"]

SOLANA_BASE58_PATTERN = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
MAX_AMOUNT_LIMIT = 100_000_000_000.0


class SecurityBaseModel(BaseModel):
    """Base model enforcing null-byte rejection and basic string hygiene."""

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_strings(cls, v: Any) -> Any:
        if isinstance(v, str) and "\x00" in v:
            raise ValueError("Null-byte injection detected: null characters ('\\0') are prohibited.")
        return v


# --- Input Models ---


class ResolveInput(SecurityBaseModel):
    """Input parameters for resolving a creator identity."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform (e.g. youtube, x, instagram)",
    )
    input: str = Field(
        min_length=1,
        max_length=128,
        description="Creator identifier, handle (e.g. @MrBeast), or profile/channel URL (1-128 chars)",
    )


class EstimateTipInput(SecurityBaseModel):
    """Input parameters for estimating token amount from USD value."""

    amount_usd: float = Field(
        gt=0,
        le=MAX_AMOUNT_LIMIT,
        description="Tip amount in USD (must be > 0 and <= 100,000,000,000)",
    )
    token_symbol: str = Field(
        default="SOL",
        min_length=1,
        max_length=32,
        description="Target token symbol (e.g. SOL, $CLAWTUBE, $CLAW)",
    )

    @field_validator("amount_usd")
    @classmethod
    def validate_finite_amount_usd(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("amount_usd must be a finite positive number")
        return v


class CreateTipTxInput(SecurityBaseModel):
    """Input parameters for building a Solana Pay tip transaction."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        min_length=1,
        max_length=64,
        description="Immutable platform UID of creator (from resolve_creator, 1-64 chars)",
    )
    donor_wallet: str = Field(
        pattern=SOLANA_BASE58_PATTERN,
        description="Donor's Solana wallet public key (32-44 character Base58 string)",
    )
    token_symbol: str = Field(
        default="SOL",
        min_length=1,
        max_length=32,
        description="Token symbol to tip (default: SOL, supports $CLAWTUBE, $CLAW)",
    )
    amount: float = Field(
        gt=0,
        le=MAX_AMOUNT_LIMIT,
        description="Token amount to tip (must be > 0 and <= 100,000,000,000)",
    )
    message: str = Field(
        default="",
        max_length=280,
        description="Optional memo or message attached to the tip (max 280 chars)",
    )
    donor_name: str = Field(
        default="",
        max_length=64,
        description="Optional donor display name (max 64 chars)",
    )

    @field_validator("amount")
    @classmethod
    def validate_finite_amount(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("amount must be a finite positive number")
        return v


class TipStatusInput(SecurityBaseModel):
    """Input parameters for verifying tip confirmation status."""

    reference_id_or_signature: str = Field(
        min_length=1,
        max_length=128,
        description="Solana transaction signature or tip reference ID (1-128 chars)",
    )


class EscrowBalanceInput(SecurityBaseModel):
    """Input parameters for querying creator escrow PDA balances."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        min_length=1,
        max_length=64,
        description="Immutable platform UID of creator (1-64 chars)",
    )


class VerifyClaimInput(SecurityBaseModel):
    """Input parameters for verifying creator claim and assembling dual-signature tx."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        min_length=1,
        max_length=64,
        description="Immutable platform UID of creator (1-64 chars)",
    )
    payout_wallet: str = Field(
        pattern=SOLANA_BASE58_PATTERN,
        description="Creator's Solana wallet public key for receiving payout (32-44 character Base58)",
    )
    auth_token: str = Field(
        min_length=1,
        max_length=512,
        description="Verification credential (OAuth access token or bio verification code, 1-512 chars)",
    )
    method: str = Field(
        default="oauth",
        min_length=1,
        max_length=32,
        description="Verification method: 'oauth' (Google/YouTube) or 'bio_code'",
    )

class RefundInput(SecurityBaseModel):
    """Input parameters for refunding an expired donor tip (days 91-120)."""

    original_tip_reference: str = Field(
        min_length=1,
        max_length=128,
        description="Original tip reference ID or escrow entry PDA (1-128 chars)",
    )


# --- Output / Result Models ---


class CreatorIdentity(SecurityBaseModel):
    """Immutable identity record for a creator across supported platforms."""

    platform: Platform
    platform_uid: str = Field(description="Immutable platform unique ID (e.g. UC_... for YouTube)")
    handle: str = Field(description="Display handle / username (e.g. @WindahBasudara)")
    display_name: str = Field(description="Human-readable channel or account name")
    avatar_url: str = Field(description="URL to channel avatar / thumbnail image")


class PriceEstimateResult(SecurityBaseModel):
    """USD to token conversion estimate."""

    amount_usd: float
    token_symbol: str
    estimated_token_amount: float
    price_usd: float
    decimals: int


class TipTxResult(SecurityBaseModel):
    """Unsigned wire transaction for donor tip."""

    wire_tx_base64: str = Field(description="Base64-encoded unsigned wire transaction for local signing")
    escrow_pda: str = Field(description="Base58 on-chain Escrow PDA address")
    instruction_count: int
    platform: Platform
    platform_uid: str
    token_symbol: str
    amount: float


class TipStatusResult(SecurityBaseModel):
    """On-chain transaction confirmation status."""

    signature: str
    confirmation_status: str = Field(description="processed | confirmed | finalized | not_found")
    slot: int | None = None
    err: str | None = None


class TokenBalance(SecurityBaseModel):
    """Token balance inside creator escrow."""

    token: str
    amount: str
    claimable: bool = True


class EscrowBalanceResult(SecurityBaseModel):
    """On-chain escrow balance details."""

    platform: Platform
    platform_uid: str
    exists: bool
    escrow_pda: str | None = None
    balances: list[TokenBalance] = Field(default_factory=list)


class ClaimResult(SecurityBaseModel):
    """Creator claim transaction payload."""

    claim_status: str = Field(description="ready | pending | completed")
    wire_tx_base64: str = Field(description="Base64 unsigned wire tx requiring Oracle + Creator signatures")
    oracle_pubkey: str | None = None
    claim_nonce: int | None = None
    expires_at: int | None = None


class RefundResult(SecurityBaseModel):
    """Donor refund transaction payload."""

    wire_tx_base64: str = Field(description="Base64 unsigned wire tx for donor refund")
    entry_pda: str
    donor_wallet: str | None = None
    refund_amount: float | None = None


