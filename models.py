"""Data models for ClawTube MCP Gateway."""

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["youtube", "x", "instagram", "threads", "tiktok", "facebook"]


# --- Input Models ---


class ResolveInput(BaseModel):
    """Input parameters for resolving a creator identity."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform (e.g. youtube, x, instagram)",
    )
    input: str = Field(
        description="Creator identifier, handle (e.g. @MrBeast), or profile/channel URL",
    )


class EstimateTipInput(BaseModel):
    """Input parameters for estimating token amount from USD value."""

    amount_usd: float = Field(
        gt=0,
        description="Tip amount in USD (must be > 0)",
    )
    token_symbol: str = Field(
        default="SOL",
        description="Target token symbol (e.g. SOL, TDROP, CLAW)",
    )


class CreateTipTxInput(BaseModel):
    """Input parameters for building a Solana Pay tip transaction."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        description="Immutable platform UID of creator (from resolve_creator)",
    )
    donor_wallet: str = Field(
        description="Donor's Solana wallet public key (Base58)",
    )
    token_symbol: str = Field(
        default="SOL",
        description="Token symbol to tip (default: SOL)",
    )
    amount: float = Field(
        gt=0,
        description="Token amount to tip (must be > 0)",
    )
    message: str = Field(
        default="",
        description="Optional memo or message attached to the tip",
    )
    donor_name: str = Field(
        default="",
        description="Optional donor display name",
    )


class TipStatusInput(BaseModel):
    """Input parameters for verifying tip confirmation status."""

    reference_id_or_signature: str = Field(
        description="Solana transaction signature or tip reference ID",
    )


class EscrowBalanceInput(BaseModel):
    """Input parameters for querying creator escrow PDA balances."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        description="Immutable platform UID of creator",
    )


class VerifyClaimInput(BaseModel):
    """Input parameters for verifying creator claim and assembling dual-signature tx."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        description="Immutable platform UID of creator",
    )
    payout_wallet: str = Field(
        description="Creator's Solana wallet public key for receiving payout",
    )
    auth_token: str = Field(
        description="Verification credential (OAuth access token or bio verification code)",
    )
    method: str = Field(
        default="upload",
        description="Verification method: 'upload', 'oauth', or 'bio'",
    )


class RefundInput(BaseModel):
    """Input parameters for refunding an expired donor tip (days 91-120)."""

    original_tip_reference: str = Field(
        description="Original tip reference ID or escrow entry PDA",
    )


class SweepInput(BaseModel):
    """Input parameters for sweeping expired escrow (>120 days) to treasury."""

    platform: Platform = Field(
        default="youtube",
        description="Target social platform",
    )
    platform_uid: str = Field(
        default="",
        description="Optional creator platform UID (empty to sweep across platform)",
    )
    dry_run: bool = Field(
        default=True,
        description="Whether to simulate sweep without generating broadcastable tx (default: True)",
    )
    sweeper_wallet: str = Field(
        default="",
        description="Solana wallet public key of sweeper claiming bounty",
    )


# --- Output / Result Models ---


class CreatorIdentity(BaseModel):
    """Immutable identity record for a creator across supported platforms."""

    platform: Platform
    platform_uid: str = Field(description="Immutable platform unique ID (e.g. UC_... for YouTube)")
    handle: str = Field(description="Display handle / username (e.g. @WindahBasudara)")
    display_name: str = Field(description="Human-readable channel or account name")
    avatar_url: str = Field(description="URL to channel avatar / thumbnail image")


class PriceEstimateResult(BaseModel):
    """USD to token conversion estimate."""

    amount_usd: float
    token_symbol: str
    estimated_token_amount: float
    price_usd: float
    decimals: int


class TipTxResult(BaseModel):
    """Unsigned wire transaction for donor tip."""

    wire_tx_base64: str = Field(description="Base64-encoded unsigned wire transaction for local signing")
    escrow_pda: str = Field(description="Base58 on-chain Escrow PDA address")
    instruction_count: int
    platform: Platform
    platform_uid: str
    token_symbol: str
    amount: float


class TipStatusResult(BaseModel):
    """On-chain transaction confirmation status."""

    signature: str
    confirmation_status: str = Field(description="processed | confirmed | finalized | not_found")
    slot: int | None = None
    err: str | None = None


class TokenBalance(BaseModel):
    """Token balance inside creator escrow."""

    token: str
    amount: str
    claimable: bool = True


class EscrowBalanceResult(BaseModel):
    """On-chain escrow balance details."""

    platform: Platform
    platform_uid: str
    exists: bool
    escrow_pda: str | None = None
    balances: list[TokenBalance] = Field(default_factory=list)


class ClaimResult(BaseModel):
    """Creator claim transaction payload."""

    claim_status: str = Field(description="ready | pending | completed")
    wire_tx_base64: str = Field(description="Base64 unsigned wire tx requiring Oracle + Creator signatures")
    oracle_pubkey: str | None = None
    claim_nonce: int | None = None
    expires_at: int | None = None


class RefundResult(BaseModel):
    """Donor refund transaction payload."""

    wire_tx_base64: str = Field(description="Base64 unsigned wire tx for donor refund")
    entry_pda: str
    donor_wallet: str | None = None
    refund_amount: float | None = None


class SweepResult(BaseModel):
    """Permissionless sweeper batch payload."""

    dry_run: bool
    eligible_entries_count: int
    wire_transactions_base64: list[str] = Field(default_factory=list)
