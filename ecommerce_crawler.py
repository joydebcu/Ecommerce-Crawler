#!/usr/bin/env python3
"""
E-commerce Product URL Crawler

This script discovers product URLs from multiple e-commerce websites.
It uses asynchronous requests to efficiently crawl websites and identify product pages
based on URL patterns and page content analysis.
"""

import asyncio
from urllib.parse import urlparse, urljoin
import re
import argparse
import json
import logging
from typing import Set, Dict, List, Tuple, Optional
import time
import random

from curl_cffi import requests as curl_requests

import aiohttp
from bs4 import BeautifulSoup
import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Common product URL patterns across e-commerce sites
PRODUCT_URL_PATTERNS = [
    # Standard product URL patterns
    r'/product[s]?/',
    r'/item[s]?/',
    r'/p/',
    r'/pd/',
    r'/buy/',
    r'/shop/',
    r'/good[s]?/',
    r'/detail/',
    r'/prod/',
    
    # Direct product patterns (without intermediate slugs)
    r'/[^/]+/p/\d+',  # Matches: /product-name/p/123456
    r'/[^/]+/\d+$',   # Matches: /product-name/123456
    r'/[^/]+-\d+$',   # Matches: /product-name-123456
    r'/[^/]+/\d+\.html$',  # Matches: /product-name/123456.html
    r'/[^/]+-\d+\.html$',  # Matches: /product-name-123456.html
    r'/[^/]+/[^/]+/p/\d+$',  # Matches: /category/product-name/p/123456
    r'/[^/]+/[^/]+/[^/]+/p/\d+$',  # Matches: /category/subcategory/product-name/p/123456
    r'/[^/]+-[^/]+-[^/]+/p/\d+$',  # Matches: /brand-product-name/p/123456
    r'/[^/]+/p-[a-z0-9]+$',  # Matches: /product-name/p-mp000000024375865
    r'/[^/]+/p-[a-z0-9]+/',  # Matches: /product-name/p-mp000000024375865/
    
    # Additional e-commerce patterns
    r'/catalog/',
    r'/collection/',
    r'/collections/',
    r'/category/',
    r'/categories/',
    r'/c/',
    r'/dp/',
    r'/sku/',
    r'/merchandise/',
    r'/merch/',
    r'/article/',
    r'/view/',
    r'/viewproduct/',
    r'/productdetail/',
    r'/productdisplay/',
    r'/productview/',
    r'/store/product/',
    r'/shop/product/',
    r'/shopping/',
    r'/listing/',
    
    # India-specific e-commerce patterns
    r'/fashion/',
    r'/clothing/',
    r'/apparel/',
    r'/wear/',
    r'/ethnic/',
    r'/accessories/',
    r'/jewellery/',
    r'/footwear/',
    r'/beauty/',
    r'/home/',
    r'/furniture/',
    r'/electronics/',
    
    # Common product identifier patterns
    r'/id\d+',
    r'/\d+\.html',
    r'/[a-z0-9]{8,}',
    
    # product with alphanumeric ID
    r'.*-p-\d+\.html',
    r'.*-pd-\d+\.html',

    r'/[^/]+/p/\d+$',  # Matches: /product-name/p/123456
    r'/c/\d+$',        # Matches: /category-path/c/6826
]

# Common product identifiers in HTML
PRODUCT_INDICATORS = [
    # Product ID attributes
    'data-product-id',
    'product-id',
    'productId',
    'data-pid',
    'data-sku',
    'sku-id',
    'skuId',
    'item-id',
    'itemId',
    'data-item-id',
    'variant-id',
    'variantId',
    
    # Add to cart indicators
    'add-to-cart',
    'add_to_cart',
    'addToCart',
    'add-to-bag',
    'add_to_bag',
    'addToBag',
    'buy-now',
    'buy_now',
    'buyNow',
    'add-to-wishlist',
    'add_to_wishlist',
    'addToWishlist',
    
    # Product detail indicators
    'product-details',
    'product_details',
    'productDetails',
    'product-description',
    'product_description',
    'productDescription',
    'product-title',
    'product_title',
    'productTitle',
    'item-details',
    'item_details',
    'itemDetails',
    
    # Price indicators
    'product-price',
    'product_price',
    'productPrice',
    'current-price',
    'current_price',
    'currentPrice',
    'sale-price',
    'sale_price',
    'salePrice',
    
    # Review indicators
    'product-reviews',
    'product_reviews',
    'productReviews',
    'customer-reviews',
    'customer_reviews',
    'customerReviews',
    
    # Size/color selectors
    'size-selector',
    'size_selector',
    'sizeSelector',
    'color-selector',
    'color_selector',
    'colorSelector',
    
    # India-specific e-commerce indicators
    'mrp',
    'buyNowButton',
    'addToBagButton',
    'pincode-check',
    'pincode_check',
    'pincodeCheck',
    'delivery-options',
    'delivery_options',
    'deliveryOptions',
    'emi-options',
    'emi_options',
    'emiOptions',
]

class EcommerceProductCrawler:
    """
    A crawler designed to discover product URLs on e-commerce websites.
    Uses asynchronous requests for efficient crawling and implements a breadth-first
    search approach to explore site structure.
    """

    def __init__(self, 
                domains: List[str], 
                max_pages_per_domain: int = 1000,
                max_concurrent_requests: int = 10,
                request_delay: float = 0.5,
                timeout: int = 30,
                user_agent: str = None):
        """
        Initialize the crawler with a list of domains to crawl.
        
        Args:
            domains: List of domains to crawl
            max_pages_per_domain: Maximum number of pages to crawl per domain
            max_concurrent_requests: Maximum number of concurrent requests
            request_delay: Delay between requests to the same domain in seconds
            timeout: Request timeout in seconds
            user_agent: User agent to use for requests
        """
        # Normalize domains
        self.domains = [self._normalize_domain(domain) for domain in domains]
        self.max_pages_per_domain = max_pages_per_domain
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.timeout = timeout
        
        # Default user agent that mimics a modern browser
        self.user_agent = user_agent or (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        
        # Keep track of visited URLs to avoid revisiting
        self.visited_urls: Dict[str, Set[str]] = {domain: set() for domain in self.domains}
        
        # Store discovered product URLs
        self.product_urls: Dict[str, Set[str]] = {domain: set() for domain in self.domains}
        
        # Domain-specific patterns discovered during crawling
        self.domain_patterns: Dict[str, List[str]] = {domain: [] for domain in self.domains}
        
        # Request timestamps to implement rate limiting
        self.last_request_time: Dict[str, float] = {domain: 0 for domain in self.domains}
        
        # Progress indicator
        self.progress_bars: Dict[str, tqdm.tqdm] = {}

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        """Normalize domain by removing trailing slash and ensuring scheme."""
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain
        return domain.rstrip('/')

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract the base domain from a URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if a URL belongs to the given domain."""
        return self._extract_domain(url) == domain
    
    def _is_product_url(self, url: str, html_content: Optional[str] = None) -> bool:
        """
        Determine if a URL is likely a product page based on URL pattern and optionally
        by analyzing the page content.
        """
        # Check URL pattern first (most efficient check)
        for pattern in PRODUCT_URL_PATTERNS + self.domain_patterns.get(self._extract_domain(url), []):
            if re.search(pattern, url):
                # Additional validation for direct product URLs
                parsed_url = urlparse(url)
                path = parsed_url.path.strip('/')
                segments = path.split('/')
                
                # Check for direct product patterns
                if len(segments) >= 2:
                    # Pattern: /product-name/p/123456 or /product-name/123456
                    if (len(segments) == 3 and segments[1] == 'p' and segments[2].isdigit()) or \
                       (len(segments) == 2 and segments[1].isdigit()):
                        return True
                    
                    # Pattern: /product-name-123456
                    if len(segments) == 1 and re.search(r'^[^/]+-\d+$', segments[0]):
                        return True
                    
                    # Pattern: /product-name/p-mp000000024375865 (Tata Cliq style)
                    if len(segments) == 2 and re.search(r'^p-[a-z0-9]+$', segments[1]):
                        return True
                
                # For other patterns, ensure minimum depth
                if len(segments) >= 3:
                    return True
        
        # If HTML content is provided, perform more detailed content analysis
        if html_content:
            # Check for product indicators in HTML attributes and text
            indicator_count = 0
            for indicator in PRODUCT_INDICATORS:
                if indicator in html_content:
                    indicator_count += 1
                    
                    # If we find multiple indicators, it's very likely a product page
                    if indicator_count >= 2:
                        # Learn this pattern for future use
                        url_path = urlparse(url).path
                        domain = self._extract_domain(url)
                        
                        # Extract potential pattern from URL
                        segments = url_path.split('/')
                        if len(segments) >= 3:
                            # Primary pattern: first directory segment
                            potential_pattern = f"/{segments[1]}/"
                            if potential_pattern not in self.domain_patterns[domain]:
                                logger.info(f"Discovered new product pattern for {domain}: {potential_pattern}")
                                self.domain_patterns[domain].append(potential_pattern)
                            
                            # If there's a second directory segment, it might be a more specific pattern
                            if len(segments) >= 4:
                                specific_pattern = f"/{segments[1]}/{segments[2]}/"
                                if specific_pattern not in self.domain_patterns[domain]:
                                    logger.info(f"Discovered specific product pattern for {domain}: {specific_pattern}")
                                    self.domain_patterns[domain].append(specific_pattern)
                        
                        return True
            
            # Additional content-based checks
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Check for product schema markup
                if 'itemtype="http://schema.org/Product"' in html_content or 'itemtype="https://schema.org/Product"' in html_content:
                    return True
                
                # Check for common product page elements
                product_title_elements = soup.select('.product-title, .product_title, .product-name, .product_name, h1.title')
                if product_title_elements:
                    return True
                
                # Look for price elements
                price_elements = soup.select('.price, .product-price, .product_price, .current-price, .current_price')
                if price_elements:
                    # Look for add to cart buttons
                    cart_buttons = soup.select('button[contains(@class, "cart")], button[contains(@class, "buy")]')
                    if cart_buttons:
                        return True
                    
            except Exception as e:
                logger.debug(f"Error in BeautifulSoup parsing: {str(e)}")
        
        return False
    
    def _extract_product_id_from_url(self, url: str) -> Optional[str]:
        """Extract product ID from URL based on domain patterns."""
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        
        if 'nykaafashion.com' in url:
            # Nykaa Fashion product pattern: /product-name/p/123456
            product_match = re.search(r'/p/(\d+)$', path)
            if product_match:
                return product_match.group(1)
            
            # Alternative pattern without the product name slug
            alt_match = re.search(r'p/(\d+)$', path)
            if alt_match:
                return alt_match.group(1)
                
            # Category pattern: /category-path/c/6826
            category_match = re.search(r'/c/(\d+)$', path)
            if category_match:
                return category_match.group(1)
        
        elif 'tatacliq.com' in url:
            # Pattern: /product-name/p-mp000000022068516
            match = re.search(r'/p-([a-z0-9]+)$', path)
            if match:
                return match.group(1)
        
        return None
    
    async def _process_product_page(self, session: aiohttp.ClientSession, url: str, domain: str) -> bool:
        """Process a product page and extract additional product URLs from API."""
        product_id = self._extract_product_id_from_url(url)
        if not product_id:
            return False
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
        }
        
        if 'nykaafashion.com' in domain:
            
            # Also try to extract category URLs for broader crawling
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        soup = BeautifulSoup(content, 'html.parser')
                        # Look for category links
                        category_links = soup.select('a[href*="/category/"], a[href*="/collection/"]')
                        for link in category_links:
                            href = link.get('href')
                            if href:
                                full_url = urljoin(domain, href)
                                if self._is_same_domain(full_url, domain):
                                    self.visited_urls[domain].add(full_url)
            except Exception as e:
                logger.error(f"Error extracting category links: {str(e)}")
        
        elif 'tatacliq.com' in domain:
            # Existing Tata Cliq handling...
            api_url = urljoin(domain, api_endpoints['product'].format(
                product_code=product_id,
                category_code='',
                brand_code='',
                price='',
                seller_id=''
            ))
            data = await self._fetch_api_data(session, api_url, domain)
            if data and 'recommendations' in data:
                for rec in data['recommendations']:
                    if 'url' in rec:
                        self.product_urls[domain].add(rec['url'])
        
        return True

    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, Optional[str]]:
        """Fetch a web page and return its content using curl_cffi for browser impersonation when needed."""
        domain = self._extract_domain(url)
        parsed_domain = urlparse(domain).netloc
        
        
        # Use site-specific delay if available
        request_delay = 2.0
        
        # Implement rate limiting
        current_time = time.time()
        elapsed = current_time - self.last_request_time[domain]
        if elapsed < request_delay:
            await asyncio.sleep(request_delay - elapsed + random.uniform(0, 0.5))
        
        self.last_request_time[domain] = time.time()
        
        # Determine whether to use curl_cffi or aiohttp based on the domain
        use_impersonation = False
        browser_profile = "chrome120"  # Default browser profile
        
        # Configure domains that need browser impersonation
        if any(site in parsed_domain for site in ["nykaafashion.com"]):
            use_impersonation = True
        
        try:
            if use_impersonation:
                # Use curl_cffi with browser impersonation for sites with anti-bot measures
                loop = asyncio.get_event_loop()
                
                # Execute the curl_cffi request in a thread pool to avoid blocking the event loop
                response = await loop.run_in_executor(
                    None,
                    lambda: curl_requests.get(
                        url,
                        impersonate=browser_profile,
                        timeout=self.timeout
                        # curl_cffi handles redirects automatically
                    )
                )
                
                if response.status_code == 200:
                    content = response.text
                    if not content or len(content) < 100:
                        logger.warning(f"Received empty or too short content from {url}")
                        return url, None
                    
                    # If this is a product page, process it for additional product URLs
                    if self._is_product_url(url, content):
                        await self._process_product_page(session, url, domain)
                    
                    return url, content
                elif response.status_code == 403:
                    logger.error(f"Access forbidden (403) for {url} - might be blocked by bot protection")
                    return url, None
                elif response.status_code == 429:
                    logger.error(f"Rate limited (429) for {url} - need to slow down")
                    await asyncio.sleep(10)  # Increased sleep time for rate limits
                    return url, None
                else:
                    logger.warning(f"Failed to fetch {url}, status: {response.status_code}")
                    return url, None
            else:
                # Use standard aiohttp for sites without strict anti-bot measures
                headers = {
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'max-age=0',
                }

                async with session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()
                        if not content or len(content) < 100:
                            logger.warning(f"Received empty or too short content from {url}")
                            return url, None
                        
                        # If this is a product page, process it for additional product URLs
                        if self._is_product_url(url, content):
                            await self._process_product_page(session, url, domain)
                        
                        return url, content
                    elif response.status == 403:
                        logger.error(f"Access forbidden (403) for {url} - might be blocked by bot protection")
                        return url, None
                    elif response.status == 429:
                        logger.error(f"Rate limited (429) for {url} - need to slow down")
                        await asyncio.sleep(10)  # Increased sleep time for rate limits
                        return url, None
                    else:
                        logger.warning(f"Failed to fetch {url}, status: {response.status}")
                        return url, None
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout while fetching {url}")
            return url, None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return url, None

    def _extract_links(self, url: str, html_content: str) -> List[str]:
        """
        Extract all links from a page and normalize them.
        """
        base_url = self._extract_domain(url)
        links = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # First, check if there's a base tag that changes the base URL for relative links
            base_tag = soup.find('base', href=True)
            base_href = base_tag['href'] if base_tag else url
            
            # Get links from standard a tags
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                # Skip empty links, javascript functions, and anchors
                if not href or href.startswith(('javascript:', '#', 'tel:', 'mailto:')):
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_href, href)
                
                # Only keep URLs from the same domain
                if self._is_same_domain(absolute_url, base_url):
                    # Normalize URL by removing fragments and query parameters
                    parsed_url = urlparse(absolute_url)
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    if parsed_url.query:
                        clean_url += f"?{parsed_url.query}"
                    links.append(clean_url)
            
            # Also look for links in product cards and other common e-commerce elements
            product_elements = soup.select('.product-card, .product-item, .product-box, .product-grid-item, [class*="product"]')
            for elem in product_elements:
                # Check for href attribute or data-url attributes
                href = None
                if elem.has_attr('href'):
                    href = elem['href']
                elif elem.has_attr('data-url') or elem.has_attr('data-href'):
                    href = elem.get('data-url') or elem.get('data-href')
                else:
                    # Check for nested link
                    link_tag = elem.find('a', href=True)
                    if link_tag:
                        href = link_tag['href']
                
                if href and not href.startswith(('javascript:', '#', 'tel:', 'mailto:')):
                    absolute_url = urljoin(base_href, href)
                    if self._is_same_domain(absolute_url, base_url):
                        parsed_url = urlparse(absolute_url)
                        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                        if parsed_url.query:
                            clean_url += f"?{parsed_url.query}"
                        links.append(clean_url)
            
            # Log the number of links found
            logger.debug(f"Found {len(links)} links on {url}")
            
        except Exception as e:
            logger.error(f"Error extracting links from {url}: {str(e)}")
        
        return list(set(links))  # Remove duplicates
    
    async def _crawl_domain(self, domain: str):
        """
        Crawl a single domain using breadth-first search to discover product URLs.
        """
        # Initialize queue with domain home page and common paths
        queue = [domain]
        common_paths = [
            '/products',
            '/shop',
            '/catalog',
            '/collection',
            '/category',
            '/fashion',
            '/clothing',
            '/apparel',
            '/accessories',
            '/footwear',
            '/beauty',
            '/new-arrivals',
            '/trending',
            '/best-sellers',
            '/deals-of-the-day',
            '/clearance-sale'
        ]
        
        for path in common_paths:
            queue.append(urljoin(domain, path))
        
        # Initialize progress bar
        self.progress_bars[domain] = tqdm.tqdm(
            total=self.max_pages_per_domain, 
            desc=f"Crawling {domain}", 
            unit="pages"
        )
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # Create HTTP session
        async with aiohttp.ClientSession(headers=headers) as session:
            while queue and len(self.visited_urls[domain]) < self.max_pages_per_domain:
                # Process pages in batches for concurrency
                batch_size = min(len(queue), self.max_concurrent_requests)
                batch = queue[:batch_size]
                queue = queue[batch_size:]
                
                # Skip already visited URLs
                batch = [url for url in batch if url not in self.visited_urls[domain]]
                if not batch:
                    continue
                
                # Fetch pages concurrently
                tasks = [self._fetch_page(session, url) for url in batch]
                results = await asyncio.gather(*tasks)
                
                # Process results
                new_urls = []
                for url, content in results:
                    self.visited_urls[domain].add(url)
                    self.progress_bars[domain].update(1)
                    
                    if content is None:
                        continue
                    
                    # Check if it's a product page
                    if self._is_product_url(url, content):
                        self.product_urls[domain].add(url)
                        logger.info(f"Found product URL: {url}")
                    
                    # Extract and queue new links
                    links = self._extract_links(url, content)
                    new_urls.extend([
                        link for link in links 
                        if link not in self.visited_urls[domain] and link not in queue
                    ])
                
                # Add new URLs to the queue
                queue.extend(new_urls)
                
                # Add a small random delay between batches
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # Log progress
                logger.info(f"Progress for {domain}: Visited {len(self.visited_urls[domain])} pages, "
                          f"Found {len(self.product_urls[domain])} products, "
                          f"Queue size: {len(queue)}")
        
        # Close progress bar
        self.progress_bars[domain].close()

    async def crawl(self):
        """Crawl all specified domains concurrently."""
        logger.info(f"Starting crawl of {len(self.domains)} domains")
        start_time = time.time()
        
        # Crawl each domain
        tasks = [self._crawl_domain(domain) for domain in self.domains]
        await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        logger.info(f"Crawl completed in {elapsed:.2f} seconds")
        logger.info(f"Discovered {sum(len(urls) for urls in self.product_urls.values())} product URLs")
    
    def get_results(self) -> Dict[str, List[str]]:
        """
        Get crawling results as a dictionary mapping domains to lists of product URLs.
        
        Returns:
            Dictionary with domains as keys and lists of product URLs as values
        """
        return {domain: list(urls) for domain, urls in self.product_urls.items()}
    
    def save_results(self, output_file: str):
        """
        Save results to a JSON file.
        
        Args:
            output_file: Path to the output file
        """
        results = self.get_results()
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
        
        # Also save stats
        stats = {
            "domains": len(self.domains),
            "total_product_urls": sum(len(urls) for urls in self.product_urls.values()),
            "product_urls_per_domain": {domain: len(urls) for domain, urls in self.product_urls.items()},
            "pages_crawled_per_domain": {domain: len(urls) for domain, urls in self.visited_urls.items()},
        }
        stats_file = output_file.replace('.json', '_stats.json')
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Stats saved to {stats_file}")

def main():
    """Main function to run the crawler from command line."""
    parser = argparse.ArgumentParser(description='E-commerce Product URL Crawler')
    parser.add_argument('--domains', nargs='+', required=True, 
                        help='List of domains to crawl')
    parser.add_argument('--output', default='product_urls.json',
                        help='Output file path (default: product_urls.json)')
    parser.add_argument('--max-pages', type=int, default=1000,
                        help='Maximum pages to crawl per domain (default: 1000)')
    parser.add_argument('--concurrency', type=int, default=10,
                        help='Maximum concurrent requests (default: 10)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Delay between requests to the same domain in seconds (default: 0.5)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Request timeout in seconds (default: 30)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--user-agent', 
                        help='User agent to use for requests')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create and run crawler
    crawler = EcommerceProductCrawler(
        domains=args.domains,
        max_pages_per_domain=args.max_pages,
        max_concurrent_requests=args.concurrency,
        request_delay=args.delay,
        timeout=args.timeout,
        user_agent=args.user_agent
    )
    
    asyncio.run(crawler.crawl())
    crawler.save_results(args.output)

if __name__ == "__main__":
    main()
