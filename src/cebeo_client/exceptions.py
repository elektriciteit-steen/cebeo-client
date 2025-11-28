"""Exceptions for the Cebeo client."""


class CebeoError(Exception):
    """Base exception for Cebeo client errors."""

    pass


class CebeoAPIError(CebeoError):
    """Error returned by the Cebeo API."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Cebeo API error {code}: {message}")


class CebeoAuthError(CebeoAPIError):
    """Authentication error from Cebeo API."""

    pass


class CebeoConnectionError(CebeoError):
    """Connection error when calling Cebeo API."""

    pass
