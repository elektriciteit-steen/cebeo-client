"""Tests for CebeoClient."""

from decimal import Decimal
from pathlib import Path

import pytest
import responses

from cebeo_client import (
    Article,
    CebeoAPIError,
    CebeoAuthError,
    CebeoClient,
    CebeoConnectionError,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Load a fixture file."""
    return (FIXTURES_DIR / name).read_text()


@pytest.fixture
def client():
    """Create a test client."""
    return CebeoClient(
        customer_number="123456",
        username="testuser",
        password="testpass",
        batch_size=50,
    )


class TestCebeoClient:
    """Test CebeoClient initialization and configuration."""

    def test_default_base_url(self):
        """Test default base URL is set."""
        client = CebeoClient("123", "user", "pass")
        assert client.base_url == "https://b2b.cebeo.be/webservices/xml"

    def test_custom_base_url(self):
        """Test custom base URL can be set."""
        client = CebeoClient("123", "user", "pass", base_url="https://test.example.com")
        assert client.base_url == "https://test.example.com"

    def test_custom_batch_size(self):
        """Test custom batch size can be set."""
        client = CebeoClient("123", "user", "pass", batch_size=100)
        assert client.batch_size == 100


class TestArticleGet:
    """Test article_get functionality."""

    @responses.activate
    def test_article_get_success(self, client):
        """Test successful article lookup."""
        responses.add(
            responses.POST,
            client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )

        articles = client.article_get(["169509", "171418", "3388164"])

        assert len(articles) == 3

        # Check first article (cable)
        cable = articles[0]
        assert cable.supplier_item_id == "169509"
        assert cable.brand_name == "INSTALLATIEKABE"
        assert cable.reference == "XVB3G2,5"
        assert cable.stock == 27300
        assert cable.stock_code == "A"
        assert cable.unit_of_measure == "MTR"
        assert cable.net_price == Decimal("2.3810")
        assert cable.vat_rate == Decimal("21.00")
        assert cable.is_available is True

        # Check second article (socket)
        socket = articles[1]
        assert socket.supplier_item_id == "171418"
        assert socket.brand_name == "NIKO"
        assert socket.net_price == Decimal("6.8500")
        assert socket.unit_of_measure == "PCE"
        assert socket.sales_pack_quantity == 10

    @responses.activate
    def test_article_get_empty_list(self, client):
        """Test with empty list returns empty."""
        articles = client.article_get([])
        assert articles == []

    @responses.activate
    def test_article_get_batching(self, client):
        """Test that large requests are batched."""
        # Create client with small batch size
        small_batch_client = CebeoClient(
            customer_number="123456",
            username="testuser",
            password="testpass",
            batch_size=2,
        )

        # Mock response
        responses.add(
            responses.POST,
            small_batch_client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )
        responses.add(
            responses.POST,
            small_batch_client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )

        # Request 3 items with batch size 2 = 2 requests
        small_batch_client.article_get(["1", "2", "3"])

        assert len(responses.calls) == 2


class TestEuropeanDecimalParsing:
    """Test European decimal format parsing."""

    @responses.activate
    def test_comma_decimal_separator(self, client):
        """Test that comma is correctly parsed as decimal separator."""
        responses.add(
            responses.POST,
            client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )

        articles = client.article_get(["169509"])

        # 2,3810 should become 2.3810
        assert articles[0].net_price == Decimal("2.3810")

        # 0,5239 should become 0.5239
        pipe = articles[2]
        assert pipe.net_price == Decimal("0.5239")


class TestErrorHandling:
    """Test error handling."""

    @responses.activate
    def test_connection_timeout(self, client):
        """Test timeout handling."""
        responses.add(
            responses.POST,
            client.base_url,
            body=responses.ConnectionError("Connection refused"),
        )

        with pytest.raises(CebeoConnectionError):
            client.article_get(["169509"])

    @responses.activate
    def test_api_error_response(self, client):
        """Test API error response handling."""
        error_response = """<?xml version="1.0" encoding="UTF-8"?>
        <cebeoXML version="2.0.0">
            <Response>
                <Message code="100">Unknown error occurred</Message>
            </Response>
        </cebeoXML>"""

        responses.add(
            responses.POST,
            client.base_url,
            body=error_response,
            status=200,
            content_type="application/xml",
        )

        with pytest.raises(CebeoAPIError) as exc_info:
            client.article_get(["169509"])

        assert exc_info.value.code == 100
        assert "Unknown error" in exc_info.value.message

    @responses.activate
    def test_auth_error_response(self, client):
        """Test authentication error handling."""
        auth_error = """<?xml version="1.0" encoding="UTF-8"?>
        <cebeoXML version="2.0.0">
            <Response>
                <Message code="1">Invalid credentials</Message>
            </Response>
        </cebeoXML>"""

        responses.add(
            responses.POST,
            client.base_url,
            body=auth_error,
            status=200,
            content_type="application/xml",
        )

        with pytest.raises(CebeoAuthError) as exc_info:
            client.article_get(["169509"])

        assert exc_info.value.code == 1


class TestArticleSearch:
    """Test article search functionality."""

    @responses.activate
    def test_search_by_keyword(self, client):
        """Test search with keywords."""
        responses.add(
            responses.POST,
            client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )

        result = client.article_search(keywords=["XVB"])

        assert result.total_count == 3
        assert len(result.articles) == 3

    @responses.activate
    def test_search_with_pagination(self, client):
        """Test search pagination."""
        responses.add(
            responses.POST,
            client.base_url,
            body=load_fixture("article_get_response.xml"),
            status=200,
            content_type="application/xml",
        )

        result = client.article_search(keywords=["test"], limit=2, offset=0)

        assert result.limit == 2
        assert result.offset == 0
        assert len(result.articles) == 2
        assert result.has_more is True

    def test_search_requires_keywords(self, client):
        """Test that search requires at least one keyword type."""
        with pytest.raises(ValueError):
            client.article_search()


class TestArticleModel:
    """Test Article dataclass."""

    def test_is_available_true(self):
        """Test is_available when stock available."""
        article = Article(
            supplier_item_id="123",
            customer_item_id=None,
            brand_code="90",
            brand_name="Test",
            reference="REF",
            description="Test article",
            stock=100,
            stock_code="A",
            unit_of_measure="PCE",
            net_price=Decimal("10.00"),
            tarif_price=Decimal("10.00"),
            ecotax=Decimal("0"),
            recupel=Decimal("0"),
            sabam=Decimal("0"),
            vat_rate=Decimal("21.00"),
            sales_pack_quantity=1,
        )
        assert article.is_available is True

    def test_is_available_false_no_stock(self):
        """Test is_available when no stock."""
        article = Article(
            supplier_item_id="123",
            customer_item_id=None,
            brand_code="90",
            brand_name="Test",
            reference="REF",
            description="Test article",
            stock=0,
            stock_code="A",
            unit_of_measure="PCE",
            net_price=Decimal("10.00"),
            tarif_price=Decimal("10.00"),
            ecotax=Decimal("0"),
            recupel=Decimal("0"),
            sabam=Decimal("0"),
            vat_rate=Decimal("21.00"),
            sales_pack_quantity=1,
        )
        assert article.is_available is False

    def test_is_available_false_wrong_code(self):
        """Test is_available when stock code not A."""
        article = Article(
            supplier_item_id="123",
            customer_item_id=None,
            brand_code="90",
            brand_name="Test",
            reference="REF",
            description="Test article",
            stock=100,
            stock_code="B",  # Not available
            unit_of_measure="PCE",
            net_price=Decimal("10.00"),
            tarif_price=Decimal("10.00"),
            ecotax=Decimal("0"),
            recupel=Decimal("0"),
            sabam=Decimal("0"),
            vat_rate=Decimal("21.00"),
            sales_pack_quantity=1,
        )
        assert article.is_available is False
