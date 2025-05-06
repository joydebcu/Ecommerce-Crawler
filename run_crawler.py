#!/usr/bin/env python3
"""
Helper script to run the crawler with the required domains.
"""

import asyncio
from ecommerce_crawler import EcommerceProductCrawler

# Required domains from the problem statement
DOMAINS = [
    "https://www.virgio.com/",
    "https://www.tatacliq.com",
    "https://nykaafashion.com/",
    "https://www.westside.com/",
]

async def main():
    # Create crawler instance
    crawler = EcommerceProductCrawler(
        domains=DOMAINS,
        max_pages_per_domain=50,  # Adjust as needed
        max_concurrent_requests=10,  # Adjust based on your internet connection
        request_delay=2.0,          # Be respectful to the websites
        timeout=10
    )
    
    # Run the crawler
    await crawler.crawl()
    
    # Save results
    crawler.save_results("product_urls.json")
    
    # Print summary
    results = crawler.get_results()
    total_products = sum(len(urls) for urls in results.values())
    
    print("\n=== Crawl Summary ===")
    print(f"Total domains crawled: {len(DOMAINS)}")
    print(f"Total product URLs found: {total_products}")
    
    for domain, urls in results.items():
        print(f"- {domain}: {len(urls)} product URLs")

if __name__ == "__main__":
    asyncio.run(main())
