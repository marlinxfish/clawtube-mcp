# ClawTube MCP Gateway Security Audit & Hardening Report

**Target**: `clawtube-mcp` (FastMCP Gateway v3.4.7)  
**Date**: 2026-08-29  
**Role**: Senior Security Auditor & MCP Hardening Engineer  
**Status**: 100% Remediated & Verified (110/110 Tests Passing)

---

## 1. Executive Summary

A comprehensive security audit of the ClawTube FastMCP gateway (`clawtube-mcp`) was conducted across all 8 protocol tools, Pydantic domain models, async HTTP backend clients, and skill provider integrations. All identified vulnerabilities were hardened using Test-Driven Development (TDD) with regression and edge-case tests in `tests/test_security.py`.

The test suite expanded from **34 baseline tests to 110 tests**, achieving complete coverage of all input boundaries, wallet validations, SSRF protections, and error sanitization paths.

---

## 2. Threat Model & Audit Checklist

| Threat Category | Risk Description | Severity | Status |
| :--- | :--- | :--- | :--- |
| **1. Wallet Address Format** | Malformed, injection-laden, or non-Base58 public keys passed to on-chain tx builders | **High** | **Remediated** |
| **2. String / Injection Boundaries** | Unbounded string lengths and null-byte (`\0`) injection leading to parsing vulnerabilities | **Medium** | **Remediated** |
| **3. Numeric Overflow / Floating-point** | `0`, negative, `NaN`, `Inf`, `-Inf`, or unbounded tip amounts causing overflow or logic bypass | **High** | **Remediated** |
| **4. Information Leakage** | Raw socket exceptions, tracebacks, internal IP/ports exposed to AI agents via error messages | **Medium** | **Remediated** |
| **5. SSRF / Unsafe Scheme** | Arbitrary or dangerous backend URLs (`file://`, `gopher://`, `ftp://`) supplied via configuration | **High** | **Remediated** |
| **6. Private Key Exposure** | Sensitive private keys, seed phrases, or mnemonics ingested, exposed, or logged | **Critical** | **Verified Clean** |
| **7. Skills Directory Traversal** | Overly broad skill root directories exposing parent repository files to AI agents | **Medium** | **Remediated** |

---

## 3. Vulnerability Findings & Remediations

### Finding 1: Solana Wallet Address Validation
- **Vulnerability**: `donor_wallet`, `payout_wallet`, and `sweeper_wallet` accepted arbitrary strings without enforcing the 32–44 character Solana Base58 format.
- **Remediation**:
  - Defined strict Solana Base58 regex pattern: `r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"`.
  - Applied regex pattern constraints to `CreateTipTxInput.donor_wallet` and `VerifyClaimInput.payout_wallet`.
  - Added dedicated `@field_validator` for `SweepInput.sweeper_wallet` permitting empty strings (optional bounty claim) while enforcing Base58 validation when provided.
  - Rejects forbidden Base58 characters (`0`, `O`, `I`, `l`), whitespace, punctuation, SQL injection payloads, and XSS strings.

### Finding 2: String Length Caps & Null-Byte Injection Defense
- **Vulnerability**: String inputs lacked explicit upper bounds and did not sanitize null bytes (`\0`), risking buffer and string termination vulnerabilities in downstream C/Rust parsers.
- **Remediation**:
  - Implemented `SecurityBaseModel` with a global `mode="before"` field validator (`sanitize_strings`) that rejects any string containing null bytes (`\x00`).
  - Added strict string length constraints across all input models:
    - `input` (creator handle/URL): `min_length=1`, `max_length=128`.
    - `platform_uid`: `min_length=1`, `max_length=64`.
    - `message`: `max_length=280`.
    - `donor_name`: `max_length=64`.
    - `reference_id_or_signature`: `min_length=1`, `max_length=128`.
    - `original_tip_reference`: `min_length=1`, `max_length=128`.
    - `auth_token`: `min_length=1`, `max_length=512`.
    - `token_symbol`: `min_length=1`, `max_length=32`.

### Finding 3: Numeric Constraints & Finite Float Enforcement
- **Vulnerability**: `amount` and `amount_usd` only had `gt=0`, allowing `float("inf")`, `float("nan")`, or astronomically large numbers exceeding integer conversion bounds.
- **Remediation**:
  - Enforced `gt=0` and `le=100_000_000_000.0` (100 billion maximum bound).
  - Added `math.isfinite` validation on `amount` and `amount_usd` in `EstimateTipInput` and `CreateTipTxInput`.

### Finding 4: Error Sanitization & Information Leakage Prevention
- **Vulnerability**: `ClawTubeClient` propagated raw `httpx.TransportError` and `httpx.ConnectError` exceptions directly in error messages (e.g. `[Errno 111] Connect call failed ('127.0.0.1', 8080)`), leaking internal network topologies and ports.
- **Remediation**:
  - Sanitized transport exceptions in `ClawTubeClient._request`:
    - `httpx.TimeoutException` maps to clean `"Request to ClawTube backend timed out. Please retry later."` (status 504).
    - `httpx.TransportError` maps to clean `"ClawTube backend is currently unreachable. Please check network connectivity and backend service status."` (status 500/503).
  - Tool execution in `server.py` catches API errors and wraps them in clean error descriptions without exposing Python tracebacks.

### Finding 5: Base URL / SSRF Protection
- **Vulnerability**: `CLAWTUBE_API_URL` environment variable and `base_url` argument allowed arbitrary URL schemes (`file://`, `ftp://`, `gopher://`, `ws://`), creating potential SSRF vectors.
- **Remediation**:
  - Added `_validate_base_url(url: str)` in `client.py` using `urllib.parse.urlparse`.
  - Enforces that schemes must strictly be `http` or `https` and requires a valid, non-empty host/netloc.
  - Rejects dangerous schemes and malformed URLs at client initialization.

### Finding 6: Zero Private Key Exposure Guarantee
- **Vulnerability / Audit Check**: Verification that no tools or models accept or leak private keys, secret seeds, or keypairs.
- **Remediation / Verification**:
  - Automated introspection tests verify that zero tool schemas or model fields contain forbidden terms (`private_key`, `secret_key`, `seed_phrase`, `mnemonic`, `keypair`).
  - Verified that all transactions returned by tools (`create_tip_tx`, `verify_creator_claim`, `refund_expired_tip`, `sweep_expired_escrow`) are base64-encoded **unsigned wire transactions** intended strictly for client-side local signing.

### Finding 7: Skills Provider Security & Traversal Protection
- **Vulnerability**: `server.py` previously registered `roots=[SKILLS_ROOT.parent, SKILLS_ROOT]`, exposing the entire parent repository (`/home/marlin/clawtube`) to the FastMCP skill provider.
- **Remediation**:
  - Replaced `SkillsDirectoryProvider` with single-skill `SkillProvider(skill_path=SKILLS_ROOT)`.
  - Added explicit directory existence and `SKILL.md` verification before provider attachment.
  - Verified that skill resource URIs only expose `skill://clawtube-skills/` and cannot traverse into other repository components.

---

## 4. Test Suite & Verification Results

### Test Execution Summary
```bash
cd clawtube-mcp && uv run pytest
```
```text
============================= test session starts ==============================
platform linux -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/marlin/clawtube/clawtube-mcp
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.14.2
asyncio: mode=Mode.AUTO, debug=False

tests/test_client.py .............                                       [ 11%]
tests/test_models.py ........                                            [ 19%]
tests/test_security.py ................................................. [ 63%]
...........................                                              [ 88%]
tests/test_server.py .                                                   [ 89%]
tests/test_skills.py .                                                   [ 90%]
tests/test_tools_1_4.py .....                                            [ 94%]
tests/test_tools_5_8.py ......                                           [100%]

============================= 110 passed in 2.04s ==============================
```

### Breakdown of Test Suites
- `tests/test_security.py` (76 tests): Complete coverage of wallet validation, boundary tests, numeric constraints, SSRF protection, null-byte rejection, error sanitization, zero private key checks, and skills isolation.
- `tests/test_client.py` (13 tests): HTTP client request assembly, retry backoff, error parsing, and transport handlers.
- `tests/test_models.py` (8 tests): Domain model serialization and base validation.
- `tests/test_tools_1_4.py` (5 tests): FastMCP tools 1 to 4 end-to-end tool execution.
- `tests/test_tools_5_8.py` (6 tests): FastMCP tools 5 to 8 end-to-end tool execution.
- `tests/test_server.py` (1 test): MCP tool registration list verification.
- `tests/test_skills.py` (1 test): MCP skill resource listing and reading.

---

## 5. Summary of Modified Files

1. `clawtube-mcp/models.py`:
   - Added `SecurityBaseModel` with null-byte rejection.
   - Added Solana Base58 regex pattern & validation.
   - Added finite & upper bound constraints on numeric fields.
   - Added string length boundaries on all inputs.
2. `clawtube-mcp/client.py`:
   - Added `_validate_base_url` for SSRF protection (scheme & host validation).
   - Sanitized transport error and timeout exception messaging.
3. `clawtube-mcp/server.py`:
   - Replaced multi-root directory provider with scoped `SkillProvider`.
   - Verified existence of `SKILLS_ROOT` and `SKILL.md`.
4. `clawtube-mcp/tests/test_security.py`:
   - Created comprehensive security test suite covering all 7 audit areas.
5. `clawtube-mcp/tests/test_models.py`, `tests/test_client.py`, `tests/test_tools_1_4.py`:
   - Updated test fixtures to use valid Solana Base58 public key fixtures.
