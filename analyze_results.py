#!/usr/bin/env python3
"""
Helper script to analyze and visualize the crawler results.
"""

import json
import argparse
from urllib.parse import urlparse
import re
from collections import Counter

def extract_path_pattern(url):
    """Extract the path pattern from a URL."""
    parsed = urlparse(url)
    path = parsed.path
    
    # Get first two segments of the path
    segments = path.split('/')
    if len(segments) >= 3:  # Must have at least /something/something
        return f"/{segments[1]}/"
    return None

def analyze_results(file_path):
    """Analyze the crawler results."""
    with open(file_path, 'r') as f:
        results = json.load(f)
    
    print("=== E-commerce Product URL Analysis ===\n")
    
    total_products = sum(len(urls) for urls in results.values())
    print(f"Total domains: {len(results)}")
    print(f"Total product URLs: {total_products}\n")
    
    for domain, urls in results.items():
        print(f"\nDomain: {domain}")
        print(f"Number of product URLs: {len(urls)}")
        
        # Analyze URL patterns
        patterns = [extract_path_pattern(url) for url in urls if extract_path_pattern(url)]
        pattern_counts = Counter(patterns)
        
        print("\nCommon URL patterns:")
        for pattern, count in pattern_counts.most_common(5):
            print(f"  {pattern}: {count} URLs ({count/len(urls)*100:.1f}%)")
        
        # Sample URLs
        if urls:
            print("\nSample product URLs:")
            for url in list(urls)[:3]:
                print(f"  {url}")
        
        print("\n" + "-"*50)

def main():
    parser = argparse.ArgumentParser(description='Analyze crawler results')
    parser.add_argument('--file', default='product_urls.json',
                      help='Path to results file (default: product_urls.json)')
    
    args = parser.parse_args()
    analyze_results(args.file)

if __name__ == "__main__":
    main()
