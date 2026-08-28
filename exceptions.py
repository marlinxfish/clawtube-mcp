"""Custom domain exceptions for ClawTube MCP Gateway."""

from typing import Any


class ClawTubeMcpError(Exception):
    """Base exception for all ClawTube MCP domain errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class PlatformUnavailableError(ClawTubeMcpError):
    """Raised when a requested social platform is disabled or not yet supported."""

    code = "PLATFORM_UNAVAILABLE"
    status_code = 503

    def __init__(self, platform: str) -> None:
        super().__init__(
            f"Platform '{platform}' is not available in phase 1. Only 'youtube' is currently enabled.",
            details={"platform": platform, "supported_platforms": ["youtube"]},
        )


class HandleNotFoundError(ClawTubeMcpError):
    """Raised when a creator handle or UID cannot be resolved."""

    code = "HANDLE_NOT_FOUND"
    status_code = 404

    def __init__(self, platform: str, identifier: str) -> None:
        super().__init__(
            f"Could not find creator '{identifier}' on platform '{platform}'. Please verify handle format.",
            details={"platform": platform, "identifier": identifier},
        )


class RateLimitedError(ClawTubeMcpError):
    """Raised when rate limits are exceeded."""

    code = "RATE_LIMITED"
    status_code = 429

    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__(
            f"Rate limit exceeded. Please retry after {retry_after_seconds} seconds.",
            details={"retry_after_seconds": retry_after_seconds},
        )


class InvalidInputError(ClawTubeMcpError):
    """Raised when input parameters fail domain validation."""

    code = "INVALID_INPUT"
    status_code = 400

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)


class BackendConnectionError(ClawTubeMcpError):
    """Raised when the ClawTube backend daemon is unreachable."""

    code = "BACKEND_UNAVAILABLE"
    status_code = 503

    def __init__(self, base_url: str) -> None:
        super().__init__(
            f"ClawTube backend is unreachable at {base_url}. Ensure the REST daemon is running on port 8080.",
            details={"base_url": base_url},
        )
