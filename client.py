"""Async HTTP client for ClawTube backend REST API with security hardening."""

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_BASE_URL = os.getenv("CLAWTUBE_API_URL", "http://localhost:8080")
DEFAULT_TOKEN_RATES: dict[str, float] = {
    "SOL": 140.0,
    "CLAWTUBE": 0.15,
    "CLAW": 0.06,
}
def _validate_base_url(url: str) -> str:
    """Validate backend base URL to prevent SSRF and unsafe schemes."""
    if not url or not isinstance(url, str):
        raise ValueError("ClawTube API base URL must be a non-empty string.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid base URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed."
        )
    if not parsed.netloc and not parsed.hostname:
        raise ValueError(
            f"Invalid base URL '{url}': Missing hostname / network location."
        )
    return url


class ClawTubeApiError(Exception):
    """Exception raised for API errors from the ClawTube backend."""

    def __init__(self, code: str | None, status: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message

    def __repr__(self) -> str:
        return f"ClawTubeApiError(code={self.code!r}, status={self.status}, message={self.message!r})"


class ClawTubeClient:
    """Async REST client for ClawTube backend daemon with retry logic and SSRF protection."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_factor: float = 0.1,
    ) -> None:
        raw_url = base_url or os.getenv("CLAWTUBE_API_URL", DEFAULT_BASE_URL)
        validated_url = _validate_base_url(raw_url)
        self._http = httpx.AsyncClient(
            base_url=validated_url, timeout=timeout, transport=transport
        )
        self._backoff_factor = backoff_factor

    async def _request(
        self, method: str, path: str, json: Any = None
    ) -> dict[str, Any]:
        """Send an HTTP request with retry on 5xx and transport errors."""
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                resp = await self._http.request(method, path, json=json)
                if resp.status_code >= 500:
                    last_error = self._parse_error_response(resp)
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(self._backoff_factor * (2**attempt))
                        continue
                    raise last_error

                if resp.status_code >= 400:
                    raise self._parse_error_response(resp)

                return resp.json()
            except httpx.TimeoutException:
                last_error = ClawTubeApiError(
                    code="TIMEOUT",
                    status=504,
                    message="Request to ClawTube backend timed out. Please retry later.",
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(self._backoff_factor * (2**attempt))
                    continue
                raise last_error
            except httpx.TransportError:
                last_error = ClawTubeApiError(
                    code="NETWORK_ERROR",
                    status=500,
                    message="ClawTube backend is currently unreachable. Please check network connectivity and backend service status.",
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(self._backoff_factor * (2**attempt))
                    continue
                raise last_error

        if last_error:
            raise last_error
        raise ClawTubeApiError(
            code="UNKNOWN_ERROR", status=500, message="Request failed after retries"
        )

    def _parse_error_response(self, resp: httpx.Response) -> ClawTubeApiError:
        code: str | None = None
        message = resp.text
        try:
            body = resp.json()
            if isinstance(body, dict):
                code = body.get("code") or body.get("error")
                message = body.get("message") or body.get("error_description") or resp.text
        except Exception:
            pass
        return ClawTubeApiError(code=code, status=resp.status_code, message=message)

    async def resolve_creator(self, platform: str, input: str) -> dict[str, Any]:
        """Resolve creator handle/URL to immutable CreatorIdentity."""
        return await self._request("POST", "/v1/resolve", json={"platform": platform, "input": input})

    async def resolve(self, platform: str, input: str) -> dict[str, Any]:
        """Alias for resolve_creator."""
        return await self.resolve_creator(platform=platform, input=input)

    async def estimate_tip_usd(self, amount_usd: float, token_symbol: str = "SOL") -> dict[str, Any]:
        """Estimate token quantity for a given USD amount with canonical protocol fallback."""
        clean_sym = token_symbol.strip().lstrip("$").upper()
        try:
            return await self._request("POST", "/v1/price", json={"amount_usd": amount_usd, "token_symbol": token_symbol})
        except ClawTubeApiError as err:
            if err.status == 404:
                rate = DEFAULT_TOKEN_RATES.get(clean_sym, 140.0 if clean_sym == "SOL" else 1.0)
                return {
                    "token_amount": amount_usd / rate,
                    "estimated_token_amount": amount_usd / rate,
                    "price_usd": rate,
                    "token_symbol": token_symbol,
                    "decimals": 9 if clean_sym == "SOL" else 6,
                    "amount_usd": amount_usd,
                }
            raise

    async def price(self, amount_usd: float, token_symbol: str = "SOL") -> dict[str, Any]:
        """Alias for estimate_tip_usd."""
        return await self.estimate_tip_usd(amount_usd=amount_usd, token_symbol=token_symbol)
    async def create_tip_tx(
        self,
        platform: str,
        platform_uid: str,
        donor_wallet: str,
        token_symbol: str,
        amount: float,
        message: str = "",
        donor_name: str = "",
    ) -> dict[str, Any]:
        """Build unsigned Solana Pay wire transaction for tip."""
        payload = {
            "platform": platform,
            "platform_uid": platform_uid,
            "donor_wallet": donor_wallet,
            "token_symbol": token_symbol,
            "amount": amount,
            "message": message,
            "donor_name": donor_name,
        }
        return await self._request("POST", "/v1/tip/tx", json=payload)

    async def verify_tip_status(self, reference_id_or_signature: str) -> dict[str, Any]:
        """Verify on-chain tip confirmation status."""
        payload = {
            "signature": reference_id_or_signature,
            "reference_id_or_signature": reference_id_or_signature,
        }
        return await self._request("POST", "/v1/tip/status", json=payload)
    async def tip_status(self, reference_id_or_signature: str) -> dict[str, Any]:
        """Alias for verify_tip_status."""
        return await self.verify_tip_status(reference_id_or_signature=reference_id_or_signature)

    async def get_creator_escrow_balance(self, platform: str, platform_uid: str) -> dict[str, Any]:
        """Get creator on-chain escrow PDA balances."""
        return await self._request("GET", f"/v1/escrow/{platform}/{platform_uid}")

    async def escrow_balance(self, platform: str, platform_uid: str) -> dict[str, Any]:
        """Alias for get_creator_escrow_balance."""
        return await self.get_creator_escrow_balance(platform=platform, platform_uid=platform_uid)

    async def verify_creator_claim(
        self,
        platform: str,
        platform_uid: str,
        payout_wallet: str,
        auth_token: str,
        method: str = "oauth",
    ) -> dict[str, Any]:
        """Validate ownership and generate dual-signature claim wire transaction."""
        payload = {
            "platform": platform,
            "platform_uid": platform_uid,
            "payout_wallet": payout_wallet,
            "credential": auth_token,
            "auth_token": auth_token,
            "method": method,
        }
        return await self._request("POST", "/v1/claim/verify", json=payload)
    async def verify_claim(
        self,
        platform: str,
        platform_uid: str,
        payout_wallet: str,
        auth_token: str,
        method: str = "upload",
    ) -> dict[str, Any]:
        """Alias for verify_creator_claim."""
        return await self.verify_creator_claim(
            platform=platform,
            platform_uid=platform_uid,
            payout_wallet=payout_wallet,
            auth_token=auth_token,
            method=method,
        )

    async def refund_expired_tip(self, original_tip_reference: str) -> dict[str, Any]:
        """Generate refund wire transaction for expired tip."""
        return await self._request("POST", "/v1/refund/tx", json={"original_tip_reference": original_tip_reference})

    async def refund_tx(self, original_tip_reference: str) -> dict[str, Any]:
        """Alias for refund_expired_tip."""
        return await self.refund_expired_tip(original_tip_reference=original_tip_reference)

    async def sweep_expired_escrow(
        self,
        platform: str = "youtube",
        platform_uid: str = "",
        dry_run: bool = True,
        sweeper_wallet: str = "",
    ) -> dict[str, Any]:
        """Generate sweep wire transaction for expired escrow (>120 days)."""
        payload = {
            "platform": platform,
            "platform_uid": platform_uid,
            "dry_run": dry_run,
            "sweeper_wallet": sweeper_wallet,
        }
        return await self._request("POST", "/v1/sweep/tx", json=payload)

    async def sweep_tx(
        self,
        platform: str = "youtube",
        platform_uid: str = "",
        dry_run: bool = True,
        sweeper_wallet: str = "",
    ) -> dict[str, Any]:
        """Alias for sweep_expired_escrow."""
        return await self.sweep_expired_escrow(
            platform=platform,
            platform_uid=platform_uid,
            dry_run=dry_run,
            sweeper_wallet=sweeper_wallet,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
