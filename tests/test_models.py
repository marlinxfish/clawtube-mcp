import pytest
from pydantic import ValidationError

from exceptions import (
    BackendConnectionError,
    ClawTubeMcpError,
    HandleNotFoundError,
    InvalidInputError,
    PlatformUnavailableError,
    RateLimitedError,
)
from models import (
    ClaimResult,
    CreateTipTxInput,
    CreatorIdentity,
    EscrowBalanceInput,
    EscrowBalanceResult,
    EstimateTipInput,
    PriceEstimateResult,
    RefundInput,
    RefundResult,
    ResolveInput,
    TipStatusInput,
    TipStatusResult,
    TipTxResult,
    TokenBalance,
    VerifyClaimInput,
)


def test_creator_identity_validation():
    identity = CreatorIdentity(
        platform="youtube",
        platform_uid="UC_ABC123XYZ",
        handle="@WindahBasudara",
        display_name="Windah Basudara",
        avatar_url="https://yt3.ggpht.com/avatar.jpg",
    )
    assert identity.platform == "youtube"
    assert identity.platform_uid == "UC_ABC123XYZ"
    assert identity.handle == "@WindahBasudara"

    # Invalid platform rejection
    with pytest.raises(ValidationError):
        CreatorIdentity(
            platform="myspace",  # type: ignore
            platform_uid="123",
            handle="test",
            display_name="test",
            avatar_url="",
        )


def test_tip_tx_result_model():
    res = TipTxResult(
        wire_tx_base64="AQAAAA==",
        escrow_pda="Escrow1111111111111111111111111111111111111",
        instruction_count=2,
        platform="youtube",
        platform_uid="UC_ABC123XYZ",
        token_symbol="SOL",
        amount=0.5,
    )
    assert res.wire_tx_base64 == "AQAAAA=="
    assert res.instruction_count == 2


def test_escrow_balance_model():
    balance = EscrowBalanceResult(
        platform="youtube",
        platform_uid="UC_ABC123XYZ",
        exists=True,
        escrow_pda="Escrow1111111111111111111111111111111111111",
        balances=[TokenBalance(token="SOL", amount="0.5", claimable=True)],
    )
    assert len(balance.balances) == 1
    assert balance.balances[0].token == "SOL"


def test_custom_domain_exceptions():
    err = PlatformUnavailableError("x")
    assert isinstance(err, ClawTubeMcpError)
    assert "x" in str(err)
    assert err.code == "PLATFORM_UNAVAILABLE"

    not_found = HandleNotFoundError("youtube", "@unknown")
    assert "@unknown" in str(not_found)
    assert not_found.code == "HANDLE_NOT_FOUND"

    rate_limit = RateLimitedError()
    assert rate_limit.code == "RATE_LIMITED"

    invalid_in = InvalidInputError("Amount must be positive")
    assert invalid_in.code == "INVALID_INPUT"

    conn_err = BackendConnectionError("http://localhost:8080")
    assert "http://localhost:8080" in str(conn_err)
    assert conn_err.code == "BACKEND_UNAVAILABLE"


def test_resolve_defaults():
    inp = ResolveInput(input="@mrbeast")
    assert inp.platform == "youtube"
    assert inp.input == "@mrbeast"

    with pytest.raises(ValidationError):
        ResolveInput()  # input required


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        EstimateTipInput(amount_usd=0)

    with pytest.raises(ValidationError):
        EstimateTipInput(amount_usd=-5.0)

    valid_est = EstimateTipInput(amount_usd=10.0)
    assert valid_est.amount_usd == 10.0
    assert valid_est.token_symbol == "SOL"

    with pytest.raises(ValidationError):
        CreateTipTxInput(
            platform="youtube",
            platform_uid="UC_ABC",
            donor_wallet="DonorW22222222222222222222222222222222",
            amount=0,
        )

    valid_tx = CreateTipTxInput(
        platform="youtube",
        platform_uid="UC_ABC",
        donor_wallet="DonorW22222222222222222222222222222222",
        amount=1.5,
    )
    assert valid_tx.amount == 1.5
    assert valid_tx.token_symbol == "SOL"
    assert valid_tx.message == ""
    assert valid_tx.donor_name == ""



def test_required_fields():
    with pytest.raises(ValidationError):
        CreateTipTxInput(platform="youtube", amount=1.0)  # missing platform_uid, donor_wallet

    with pytest.raises(ValidationError):
        VerifyClaimInput(platform="youtube", platform_uid="UC_ABC")  # missing payout_wallet, auth_token

    with pytest.raises(ValidationError):
        EscrowBalanceInput(platform="youtube")  # missing platform_uid

    with pytest.raises(ValidationError):
        RefundInput()  # missing original_tip_reference

    with pytest.raises(ValidationError):
        TipStatusInput()  # missing reference_id_or_signature
