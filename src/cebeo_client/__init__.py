"""Cebeo B2B XML API client.

A Python client for interacting with Cebeo's B2B XML web services.
"""

from .client import CebeoClient
from .exceptions import CebeoAPIError, CebeoAuthError, CebeoConnectionError, CebeoError
from .models import Article, ArticleSearchResult, Order, OrderLine

__version__ = "0.1.0"

__all__ = [
    "CebeoClient",
    "Article",
    "ArticleSearchResult",
    "Order",
    "OrderLine",
    "CebeoError",
    "CebeoAPIError",
    "CebeoAuthError",
    "CebeoConnectionError",
]
