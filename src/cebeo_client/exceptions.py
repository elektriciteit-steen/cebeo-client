"""Exceptions for the Cebeo client."""


class CebeoError(Exception):
    """Base exception for Cebeo client errors."""

    pass


class CebeoAPIError(CebeoError):
    """Error returned by the Cebeo API.

    Args:
        code: Numeric status code from the ``<Message code="...">`` attribute.
        message: Message text payload from the ``<Message>`` element.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Cebeo API error {code}: {message}")


class CebeoAuthError(CebeoAPIError):
    """Authentication error from the Cebeo API.

    Raised for genuine credential/access failures: invalid or inactive
    user, invalid password, no web-service access, invalid/ambiguous
    customer. Callers should treat this as a hard stop — the run cannot
    succeed with broken credentials.
    """

    pass


class CebeoArticleNotFoundError(CebeoAPIError):
    """A referenced article was not found in the Cebeo catalog.

    The Cebeo API reuses numeric status code ``1`` for several unrelated
    conditions (authentication failures *and* article errors), so the
    numeric code alone cannot tell a caller whether their credentials are
    broken or the article simply does not exist. The actual condition is
    carried by the message payload: ``ART0011`` means "article not found".

    This is a normal miss (e.g. during a bulk article sweep), not a
    credential failure, so it is surfaced as a distinct, catchable
    condition rather than as :class:`CebeoAuthError`. Callers can
    distinguish the two by exception type — no string-matching required:

    .. code-block:: python

        try:
            client.article_get(["UNKNOWN"])
        except CebeoArticleNotFoundError:
            ...  # routine miss, keep going
        except CebeoAuthError:
            ...  # credentials broken, abort
    """

    pass


class CebeoConnectionError(CebeoError):
    """Connection error when calling Cebeo API."""

    pass
