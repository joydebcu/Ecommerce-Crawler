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
from collections import defaultdict

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
    r'/product[s]?/',
    r'/item[s]?/',
    r'/p/',
    r'/pd/',
    r'/buy/',
    r'/shop/',
    r'/good[s]?/',
    r'/detail/',
    r'/prod/',
]

# Common product identifiers in HTML
PRODUCT_INDICATORS = [
    'data-product-id',
    'product-id',
    'productId',
    'data-pid',
    'add-to-cart',
    'data-sku',
    'add_to_cart',
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
            domains: List of e-commerce domains to crawl
            max_pages_per_domain: Maximum number of pages to crawl per domain
            max_concurrent_requests: Maximum number of concurrent requests
            request_delay: Delay between requests to the same domain (in seconds)
            timeout: Request timeout in seconds
            user_agent: Custom user agent string
        """
        # Normalize domains
        self.domains = [self._normalize_domain(domain) for domain in domains]
        self.max_pages_per_domain = max_pages_per_domain
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.timeout = timeout
        
        # Default user agent that mimics a real browser
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
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
        # Check URL pattern
        for pattern in PRODUCT_URL_PATTERNS + self.domain_patterns.get(self._extract_domain(url), []):
            if re.search(pattern, url):
                return True
        
        # If HTML content is provided, check for product indicators
        if html_content:
            for indicator in PRODUCT_INDICATORS:
                if indicator in html_content:
                    # Learn this pattern for future use
                    url_path = urlparse(url).path
                    domain = self._extract_domain(url)
                    
                    # Extract potential pattern from URL
                    segments = url_path.split('/')
                    if len(segments) >= 3:  # Must have at least /something/something
                        potential_pattern = f"/{segments[1]}/"
                        if potential_pattern not in self.domain_patterns[domain]:
                            logger.info(f"Discovered new product pattern for {domain}: {potential_pattern}")
                            self.domain_patterns[domain].append(potential_pattern)
                    
                    return True
        
        return False
    
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, Optional[str]]:
        """
        Fetch a web page and return its content.
        
        Args:
            session: aiohttp client session
            url: URL to fetch
            
        Returns:
            Tuple of (URL, HTML content or None if failed)
        """
        domain = self._extract_domain(url)
        
        # Implement rate limiting
        current_time = time.time()
        elapsed = current_time - self.last_request_time[domain]
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed + random.uniform(0, 0.5))
        
        self.last_request_time[domain] = time.time()
        
        try:
            async with session.get(url, timeout=self.timeout) as response:
                if response.status == 200:
                    content = await response.text()
                    return url, content
                else:
                    logger.warning(f"Failed to fetch {url}, status: {response.status}")
                    return url, None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return url, None
    
    def _extract_links(self, url: str, html_content: str) -> List[str]:
        """
        Extract all links from a page and normalize them.
        
        Args:
            url: Source URL
            html_content: HTML content of the page
            
        Returns:
            List of normalized absolute URLs
        """
        base_url = self._extract_domain(url)
        links = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                # Convert relative URLs to absolute
                absolute_url = urljoin(url, href)
                
                # Only keep URLs from the same domain
                if self._is_same_domain(absolute_url, base_url):
                    # Normalize URL by removing fragments and query parameters
                    parsed_url = urlparse(absolute_url)
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    links.append(clean_url)
        except Exception as e:
            logger.error(f"Error extracting links from {url}: {str(e)}")
        
        return list(set(links))  # Remove duplicates
    
    async def _crawl_domain(self, domain: str):
        """
        Crawl a single domain using breadth-first search to discover product URLs.
        
        Args:
            domain: Domain to crawl
        """
        # Initialize queue with domain homepage
        queue = [domain]
        
        # Initialize progress bar
        self.progress_bars[domain] = tqdm.tqdm(
            total=self.max_pages_per_domain, 
            desc=f"Crawling {domain}", 
            unit="pages"
        )
        
        # Create HTTP session
        async with aiohttp.ClientSession(headers={"User-Agent": self.user_agent}) as session:
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
                        logger.debug(f"Found product URL: {url}")
                    
                    # Extract and queue new links
                    links = self._extract_links(url, content)
                    new_urls.extend([
                        link for link in links 
                        if link not in self.visited_urls[domain] and link not in queue
                    ])
                
                # Add new URLs to the queue
                queue.extend(new_urls)
        
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
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create and run crawler
    crawler = EcommerceProductCrawler(
        domains=args.domains,
        max_pages_per_domain=args.max_pages,
        max_concurrent_requests=args.concurrency,
        request_delay=args.delay,
        timeout=args.timeout
    )
    
    asyncio.run(crawler.crawl())
    crawler.save_results(args.output)

if __name__ == "__main__":
    main()
