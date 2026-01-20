from scraper import Scraper
import json
import os

def test_full_flow():
    scraper = Scraper()
    username = "davidehrlich"
    print(f"Testing full scrape flow for {username}...")
    
    # 1. Scrape
    entries = scraper.scrape_user(username)
    print(f"Result count: {len(entries)}")
    
    if entries:
        print("First entry sample:")
        print(entries[0])
    else:
        print("Failed to find entries (parsed 0 rows).")

if __name__ == "__main__":
    test_full_flow()
