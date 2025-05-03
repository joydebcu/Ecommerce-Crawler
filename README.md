# E-commerce Product URL Crawler

A Python-based web crawler designed to discover product URLs on e-commerce websites. The crawler implements a breadth-first search approach and uses asynchronous requests to efficiently explore websites, identify product pages, and compile a list of product URLs.

## Features

- **Intelligent URL Discovery**: Automatically identifies product pages using URL patterns and content analysis
- **Adaptive Pattern Learning**: Learns new product URL patterns specific to each domain during crawling
- **Scalable Architecture**: Handles multiple domains concurrently with asynchronous processing
- **Rate Limiting**: Respects website resources with configurable request delays
- **Progress Tracking**: Real-time progress indicators for each domain being crawled
- **Comprehensive Output**: Provides detailed results with statistics

## Approach to Finding Product URLs

The crawler employs multiple strategies to identify product URLs:

### 1. URL Pattern Recognition

The crawler looks for common e-commerce product URL patterns such as:
- `/product/`
- `/item/`
- `/p/`
- `/pd/`
- `/buy/`
- `/shop/`
- `/goods/`
- `/detail/`
- `/prod/`

### 2. Adaptive Pattern Learning

As the crawler explores each website, it analyzes page content for product indicators such as:
- `data-product-id` attributes
- "Add to cart" buttons
- SKU identifiers
- Product detail sections

When it finds these indicators, it learns the URL pattern of that page and adds it to its domain-specific pattern list, improving detection for subsequent pages.

### 3. Breadth-First Search

The crawler uses a breadth-first search approach to systematically explore the website structure:
1. Start at the homepage
2. Extract all links from the current page
3. Filter links to keep only those from the same domain
4. Queue new links for processing
5. Identify and save product URLs
6. Continue until reaching the maximum page limit or exhausting all pages

### 4. Parallel Processing

To handle large websites efficiently, the crawler:
- Processes multiple domains concurrently
- Makes multiple requests in parallel within each domain
- Implements rate limiting to respect web server resources

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ecommerce-product-crawler.git
cd ecommerce-product-crawler

# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python ecommerce_crawler.py --domains www.virgio.com www.tatacliq.com nykaafashion.com www.westside.com --output product_urls.json
```

### Advanced Options

```bash
python ecommerce_crawler.py \
  --domains www.virgio.com www.tatacliq.com nykaafashion.com www.westside.com \
  --output product_urls.json \
  --max-pages 2000 \
  --concurrency 15 \
  --delay 0.3 \
  --timeout 20 \
  --debug
```

### Command Line Arguments

- `--domains`: List of domains to crawl (required)
- `--output`: Output file path (default: product_urls.json)
- `--max-pages`: Maximum pages to crawl per domain (default: 1000)
- `--concurrency`: Maximum concurrent requests (default: 10)
- `--delay`: Delay between requests to the same domain in seconds (default: 0.5)
- `--timeout`: Request timeout in seconds (default: 30)
- `--debug`: Enable debug logging

## Output Format

The crawler saves results in JSON format:

```json
{
  "https://www.example.com": [
    "https://www.example.com/product/12345",
    "https://www.example.com/product/67890",
    ...
  ],
  "https://www.another-site.com": [
    "https://www.another-site.com/item/abc123",
    "https://www.another-site.com/item/def456",
    ...
  ]
}
```

Additionally, it generates a statistics file with information about the crawl:

```json
{
  "domains": 4,
  "total_product_urls": 3627,
  "product_urls_per_domain": {
    "https://www.example.com": 1245,
    "https://www.another-site.com": 982,
    ...
  },
  "pages_crawled_per_domain": {
    "https://www.example.com": 1000,
    "https://www.another-site.com": 1000,
    ...
  }
}
```

## Performance Considerations

- **Memory Usage**: The crawler maintains sets of visited URLs and discovered product URLs in memory. For extremely large websites, this may require significant memory.
- **Rate Limiting**: The default delay between requests to the same domain is 0.5 seconds. Adjust this based on the website's terms of service and server capacity.
- **Timeout**: The default request timeout is 30 seconds. Lower this value for faster crawling but potentially more failed requests.
- **Maximum Pages**: The default maximum pages per domain is 1000. Increase this for more comprehensive crawling of large websites.

## Extending the Crawler

### Adding Custom Product Indicators

Edit the `PRODUCT_INDICATORS` list in the code to add custom product page indicators:

```python
PRODUCT_INDICATORS = [
    'data-product-id',
    'product-id',
    'productId',
    'data-pid',
    'add-to-cart',
    'data-sku',
    'add_to_cart',
    # Add your custom indicators here
    'your-custom-indicator',
]
```

### Adding Custom URL Patterns

Edit the `PRODUCT_URL_PATTERNS` list in the code to add custom product URL patterns:

```python
PRODUCT_URL_PATTERNS = [
    r'/product[s]?/',
    r'/item[s]?/',
    r'/p/',
    # Add your custom patterns here
    r'/your-custom-pattern/',
]
```

## License

MIT

## Author

Joy deb