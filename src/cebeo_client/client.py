"""Cebeo B2B XML API client."""

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import requests

from .exceptions import CebeoAPIError, CebeoAuthError, CebeoConnectionError
from .models import Article, ArticleSearchResult, Order, OrderLine

# Default API endpoint
DEFAULT_BASE_URL = "https://b2b.cebeo.be/webservices/xml"

# XML namespace and schema info
XML_VERSION = "2.0.0"
XML_SCHEMA_LOCATION = "http://b2b.cebeo.be/XMLschema/2.0.0/cebeoXML.xsd"


def _parse_european_decimal(value: str) -> Decimal:
    """Parse European decimal format (comma as separator).

    Examples:
        '2,3810' -> Decimal('2.3810')
        '0,0000' -> Decimal('0.0000')
        '21,00' -> Decimal('21.00')
    """
    if not value:
        return Decimal("0")
    return Decimal(value.replace(",", "."))


def _parse_int(value: str) -> int:
    """Parse integer, returning 0 for empty strings."""
    if not value:
        return 0
    return int(value)


def _get_text(element: ET.Element, path: str, default: str = "") -> str:
    """Get text content from an element path, with default."""
    child = element.find(path)
    if child is not None and child.text:
        return child.text
    return default


def _parse_date(element: ET.Element) -> date | None:
    """Parse a Cebeo date element (Day/Month/Year sub-elements).

    Args:
        element: Element containing Day, Month, Year children

    Returns:
        date object or None if invalid/missing
    """
    if element is None:
        return None

    day = element.find("Day")
    month = element.find("Month")
    year = element.find("Year")

    if day is None or month is None or year is None:
        return None

    try:
        return date(
            year=int(year.text or 0),
            month=int(month.text or 0),
            day=int(day.text or 0),
        )
    except (ValueError, TypeError):
        return None


class CebeoClient:
    """Client for the Cebeo B2B XML API.

    Args:
        customer_number: Cebeo customer number
        username: E-shop username
        password: E-shop password
        base_url: API endpoint URL (defaults to production)
        timeout: Request timeout in seconds
        batch_size: Max articles per API request (default 50)
    """

    def __init__(
        self,
        customer_number: str,
        username: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        batch_size: int = 50,
    ):
        self.customer_number = customer_number
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout = timeout
        self.batch_size = batch_size

    def _build_request_xml(self, operation_element: ET.Element, response_type: str = "List") -> str:
        """Build a complete request XML document.

        Args:
            operation_element: The operation-specific element (Article/Order)
            response_type: ResponseType value - "List", "Detail", or "Message"

        Returns:
            Complete XML string ready to send
        """
        root = ET.Element("cebeoXML")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", XML_SCHEMA_LOCATION)
        root.set("version", XML_VERSION)

        request = ET.SubElement(root, "Request")

        # Customer authentication
        customer = ET.SubElement(request, "Customer")
        ET.SubElement(customer, "CustomerNumber").text = self.customer_number
        ET.SubElement(customer, "UserName").text = self.username
        ET.SubElement(customer, "Password").text = self.password

        # Response type
        ET.SubElement(request, "ResponseType").text = response_type

        # Add the operation element
        request.append(operation_element)

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _send_request(self, xml_body: str) -> ET.Element:
        """Send XML request and parse response.

        Args:
            xml_body: The XML request body

        Returns:
            Parsed response XML element

        Raises:
            CebeoConnectionError: On connection issues
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        try:
            response = requests.post(
                self.base_url,
                data=xml_body.encode("utf-8"),
                headers={"Content-Type": "application/xml; charset=utf-8"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise CebeoConnectionError(f"Request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise CebeoConnectionError(f"Connection failed: {e}") from e
        except requests.exceptions.HTTPError as e:
            raise CebeoConnectionError(f"HTTP error: {e}") from e

        # Parse response XML
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise CebeoAPIError(-1, f"Invalid XML response: {e}") from e

        # Check for error response
        resp_element = root.find("Response")
        if resp_element is None:
            raise CebeoAPIError(-1, "Missing Response element in XML")

        message = resp_element.find("Message")
        if message is not None:
            code = int(message.get("code", "0"))
            msg_text = message.text or ""

            # Code 0 = success
            if code != 0:
                # Authentication errors typically have specific codes
                if code in (1, 2, 3):  # Common auth error codes
                    raise CebeoAuthError(code, msg_text)
                raise CebeoAPIError(code, msg_text)

        return resp_element

    def _parse_article(self, item: ET.Element) -> Article:
        """Parse an Item element into an Article dataclass."""
        material = item.find("Material")
        unit_price = item.find("UnitPrice")

        return Article(
            supplier_item_id=_get_text(material, "SupplierItemID"),
            customer_item_id=_get_text(material, "CustomerItemID") or None,
            brand_code=_get_text(material, "BrandCode"),
            brand_name=_get_text(material, "BrandName"),
            reference=_get_text(material, "Reference"),
            description=_get_text(material, "Description"),
            reel_code=_get_text(material, "ReelCode") or None,
            reel_length=_parse_int(_get_text(material, "ReelLength")) or None,
            promotion_code=_get_text(material, "PromotionCode") or None,
            stock_code=_get_text(item, "StockCode"),
            stock=_parse_int(_get_text(item, "Stock")),
            unit_of_measure=_get_text(item, "UnitOfMeasure"),
            net_price=_parse_european_decimal(_get_text(unit_price, "NetPrice")),
            tarif_price=_parse_european_decimal(_get_text(unit_price, "TarifPrice")),
            ecotax=_parse_european_decimal(_get_text(unit_price, "Ecotax")),
            recupel=_parse_european_decimal(_get_text(unit_price, "Recupel")),
            sabam=_parse_european_decimal(_get_text(unit_price, "Sabam")),
            vat_rate=_parse_european_decimal(_get_text(unit_price, "TAV")),
            sales_pack_quantity=_parse_int(_get_text(item, "SalesPackQuantity")),
        )

    def article_get(self, supplier_item_ids: list[str]) -> list[Article]:
        """Get articles by their Cebeo supplier item IDs.

        Automatically batches requests if more items than batch_size.

        Args:
            supplier_item_ids: List of Cebeo article IDs to look up

        Returns:
            List of Article objects for found items

        Raises:
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        if not supplier_item_ids:
            return []

        articles = []

        # Process in batches
        for i in range(0, len(supplier_item_ids), self.batch_size):
            batch = supplier_item_ids[i : i + self.batch_size]
            batch_articles = self._article_get_batch(batch)
            articles.extend(batch_articles)

        return articles

    def _article_get_batch(self, supplier_item_ids: list[str]) -> list[Article]:
        """Get a single batch of articles."""
        # Build Article/Get element
        article = ET.Element("Article")
        get = ET.SubElement(article, "Get")

        for item_id in supplier_item_ids:
            material = ET.SubElement(get, "Material")
            ET.SubElement(material, "SupplierItemID").text = item_id

        xml_body = self._build_request_xml(article)
        response = self._send_request(xml_body)

        # Parse articles from response
        articles = []
        article_list = response.find("Article/List")
        if article_list is not None:
            for item in article_list.findall("Item"):
                articles.append(self._parse_article(item))

        return articles

    def article_search(
        self,
        keywords: list[str] | None = None,
        brand_keywords: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ArticleSearchResult:
        """Search for articles by keywords and/or brand.

        Args:
            keywords: Search keywords for article reference/description
            brand_keywords: Keywords to filter by brand
            limit: Maximum number of results (default 20)
            offset: Starting offset for pagination (default 0)

        Returns:
            ArticleSearchResult with articles and pagination info

        Raises:
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        if not keywords and not brand_keywords:
            raise ValueError("At least one of keywords or brand_keywords required")

        # Build Article/Search element
        article = ET.Element("Article")
        search = ET.SubElement(article, "Search")

        if keywords:
            search_keywords = ET.SubElement(search, "SearchKeywords")
            for kw in keywords:
                ET.SubElement(search_keywords, "Keyword").text = kw

        if brand_keywords:
            brand_kw = ET.SubElement(search, "BrandKeywords")
            for kw in brand_keywords:
                ET.SubElement(brand_kw, "Keyword").text = kw

        # Note: Cebeo API pagination is handled differently
        # The API returns all matching results in the List response

        xml_body = self._build_request_xml(article)
        response = self._send_request(xml_body)

        # Parse articles from response
        articles = []
        total_count = 0

        article_list = response.find("Article/List")
        if article_list is not None:
            num_lines = article_list.find("NumberOfLines")
            if num_lines is not None and num_lines.text:
                total_count = int(num_lines.text)

            for item in article_list.findall("Item"):
                articles.append(self._parse_article(item))

        # Apply client-side pagination if needed
        # (Cebeo API returns all results, we slice here)
        paginated_articles = articles[offset : offset + limit]

        return ArticleSearchResult(
            articles=paginated_articles,
            total_count=total_count,
            offset=offset,
            limit=limit,
        )

    def _parse_order_line(self, line_elem: ET.Element) -> OrderLine:
        """Parse an OrderLine element into an OrderLine dataclass."""
        material = line_elem.find("Material")
        unit_price = line_elem.find("UnitPrice")

        return OrderLine(
            supplier_order_line_id=_get_text(line_elem, "SupplierOrderLineID"),
            supplier_item_id=_get_text(material, "SupplierItemID") if material else "",
            description=_get_text(material, "Description") if material else "",
            unit_of_measure=_get_text(line_elem, "UnitOfMeasure"),
            ordered_quantity=_parse_int(_get_text(line_elem, "OrderedQuantity")),
            net_price=_parse_european_decimal(
                _get_text(unit_price, "NetPrice") if unit_price else ""
            ),
            stock=_parse_int(_get_text(line_elem, "Stock")),
            stock_code=_get_text(line_elem, "StockCode"),
            customer_order_line_id=_get_text(line_elem, "CustomerOrderLineID") or None,
            customer_item_id=(_get_text(material, "CustomerItemID") if material else None) or None,
            ean=(_get_text(material, "EAN") if material else None) or None,
            brand_code=_get_text(material, "BrandCode") if material else None,
            brand_name=_get_text(material, "BrandName") if material else None,
            reference=_get_text(material, "Reference") if material else None,
            reel_code=(_get_text(material, "ReelCode") if material else None) or None,
            reel_length=(_parse_int(_get_text(material, "ReelLength")) if material else None)
            or None,
            backorder_quantity=_parse_int(_get_text(line_elem, "BOQuantity")) or None,
            backorder_delivery_date=_parse_date(line_elem.find("BOEstimatedDeliveryDate")),
            delivery_quantity=_parse_int(_get_text(line_elem, "DeliveryQuantity")) or None,
            delivery_date=_parse_date(line_elem.find("DeliveryDate")),
            requested_delivery_date=_parse_date(line_elem.find("RequestedDeliveryDate")),
        )

    def _parse_order(self, detail_elem: ET.Element) -> Order:
        """Parse an Order/Detail element into an Order dataclass."""
        header = detail_elem.find("OrderHeader")
        if header is None:
            raise CebeoAPIError(-1, "Missing OrderHeader in response")

        # Parse order lines
        lines = []
        for line_elem in detail_elem.findall("OrderLine"):
            lines.append(self._parse_order_line(line_elem))

        # Parse comments (there can be multiple)
        comments = []
        for comment_elem in header.findall("Comments"):
            if comment_elem.text:
                comments.append(comment_elem.text)

        # Parse delivery address if present
        delivery_address = None
        delivery_loc = header.find("DeliveryLocation")
        if delivery_loc is not None:
            addr_elem = delivery_loc.find("DeliveryAddress")
            if addr_elem is not None:
                delivery_address = {
                    "deliver_to": _get_text(addr_elem, "DeliverTo"),
                    "street": _get_text(addr_elem, "Street"),
                    "postal_code": _get_text(addr_elem, "PostalCode"),
                    "city": _get_text(addr_elem, "City"),
                }
            # Include contact info if present
            contact = _get_text(delivery_loc, "ContactPerson")
            if contact and delivery_address:
                delivery_address["contact_person"] = contact
            phone = _get_text(delivery_loc, "ContactTelephone")
            if phone and delivery_address:
                delivery_address["contact_telephone"] = phone

        return Order(
            supplier_order_id=_get_text(header, "SupplierOrderID"),
            customer_order_id=_get_text(header, "CustomerOrderID"),
            order_date=_parse_date(header.find("OrderDate")) or date.today(),
            lines=lines,
            customer_order_ref=_get_text(header, "CustomerOrderRef") or None,
            ordered_by=_get_text(header, "OrderedBy") or None,
            delivery_address=delivery_address,
            comments=comments if comments else None,
        )

    def order_get(
        self,
        supplier_order_id: str | None = None,
        customer_order_id: str | None = None,
        open_order: bool = False,
    ) -> Order | None:
        """Fetch an order from Cebeo.

        Args:
            supplier_order_id: Cebeo's order ID (SupplierOrderID)
            customer_order_id: Customer's order reference (CustomerOrderID)
            open_order: If True, fetch the open/shopping cart order

        Returns:
            Order object, or None if not found

        Raises:
            ValueError: If no identifier is provided
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        if not any([supplier_order_id, customer_order_id, open_order]):
            raise ValueError(
                "Must provide supplier_order_id, customer_order_id, or open_order=True"
            )

        # Build Order/Get element
        order_elem = ET.Element("Order")
        get = ET.SubElement(order_elem, "Get")

        if open_order:
            ET.SubElement(get, "OpenOrder")
        elif supplier_order_id:
            ET.SubElement(get, "SupplierOrderID").text = supplier_order_id
        elif customer_order_id:
            ET.SubElement(get, "CustomerOrderID").text = customer_order_id

        xml_body = self._build_request_xml(order_elem, response_type="Detail")
        response = self._send_request(xml_body)

        # Parse order from response
        order_detail = response.find("Order/Detail")
        if order_detail is None:
            return None

        return self._parse_order(order_detail)

    def order_get_open(self) -> Order | None:
        """Fetch the open order from the e-shop cart.

        This retrieves the "shopping cart" - items added to the e-shop
        but not yet confirmed. Only one open order exists per customer.

        Returns:
            Order object with cart contents, or None if no open order exists

        Raises:
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        return self.order_get(open_order=True)

    def order_delete(
        self,
        supplier_order_id: str | None = None,
        open_order: bool = False,
    ) -> bool:
        """Delete an order from Cebeo.

        Args:
            supplier_order_id: Cebeo's order ID to delete
            open_order: If True, delete the open/shopping cart order

        Note: Cannot delete orders that are already confirmed/closed.

        Returns:
            True if order was deleted successfully

        Raises:
            ValueError: If no identifier is provided
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        if not any([supplier_order_id, open_order]):
            raise ValueError("Must provide supplier_order_id or open_order=True")

        # Build Order/Delete element
        order_elem = ET.Element("Order")
        delete = ET.SubElement(order_elem, "Delete")

        if open_order:
            ET.SubElement(delete, "OpenOrder")
        elif supplier_order_id:
            ET.SubElement(delete, "SupplierOrderID").text = supplier_order_id

        xml_body = self._build_request_xml(order_elem, response_type="Message")
        self._send_request(xml_body)

        return True

    def order_delete_open(self) -> bool:
        """Delete the open order from the e-shop cart.

        This clears the shopping cart. Typically called after importing
        the cart contents into an external system.

        Note: Cannot delete orders that are already confirmed/closed.

        Returns:
            True if order was deleted successfully

        Raises:
            CebeoAPIError: On API errors
            CebeoAuthError: On authentication errors
        """
        return self.order_delete(open_order=True)
