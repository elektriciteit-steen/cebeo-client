# cebeo-client

Python client for Cebeo's B2B XML API.

## Installation

```bash
pip install cebeo-client
```

## Usage

```python
from cebeo_client import CebeoClient

client = CebeoClient(
    customer_number="123456",
    username="your_username",
    password="your_password",
)

# Lookup articles by Cebeo article IDs
articles = client.article_get(["169509", "171418"])
for article in articles:
    print(f"{article.supplier_item_id}: {article.description}")
    print(f"  Price: {article.net_price} EUR")
    print(f"  Stock: {article.stock} ({article.stock_code})")
    print(f"  Available: {article.is_available}")

# Search for articles
result = client.article_search(keywords=["XVB"], brand_keywords=["Niko"])
print(f"Found {result.total_count} articles")
for article in result.articles:
    print(f"  {article.reference}: {article.description}")
```

## Configuration

```python
client = CebeoClient(
    customer_number="123456",
    username="user",
    password="pass",
    base_url="https://b2b.cebeo.be/webservices/xml",  # default
    timeout=30,      # request timeout in seconds
    batch_size=50,   # max articles per API request
)
```

## Error Handling

```python
from cebeo_client import CebeoAPIError, CebeoAuthError, CebeoConnectionError

try:
    articles = client.article_get(["123"])
except CebeoAuthError as e:
    print(f"Authentication failed: {e}")
except CebeoAPIError as e:
    print(f"API error {e.code}: {e.message}")
except CebeoConnectionError as e:
    print(f"Connection failed: {e}")
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src tests
```

## License

MIT
