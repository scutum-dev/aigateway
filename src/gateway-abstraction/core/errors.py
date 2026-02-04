"""
Gateway abstraction error types.
"""


class GatewayError(Exception):
    """Base exception for gateway errors."""

    def __init__(self, message: str, gateway: str = None):
        self.message = message
        self.gateway = gateway
        super().__init__(message)


class GatewayNotFoundError(GatewayError):
    """Raised when a gateway is not found."""
    pass


class GatewayConnectionError(GatewayError):
    """Raised when connection to gateway fails."""
    pass


class GatewayAuthenticationError(GatewayError):
    """Raised when authentication fails."""
    pass


class GatewayRateLimitError(GatewayError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, gateway: str = None, retry_after: float = None):
        super().__init__(message, gateway)
        self.retry_after = retry_after


class GatewayTimeoutError(GatewayError):
    """Raised when request times out."""
    pass


class GatewayModelNotFoundError(GatewayError):
    """Raised when requested model is not available."""

    def __init__(self, message: str, gateway: str = None, model: str = None):
        super().__init__(message, gateway)
        self.model = model


class GatewayInvalidRequestError(GatewayError):
    """Raised when request is invalid."""
    pass
