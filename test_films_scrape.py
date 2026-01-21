from scraper import Scraper
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)

def test():
    s = Scraper()
    # Use a populous profile
    user = "cheesesocrates" 
    print(f"Testing films scrape for {user}...")
    
    # Try page 1 of films
    res = s.scrape_films_page(user, 1)
    entries = res['entries']
    print(f"Found {len(entries)} entries.")
    if entries:
        print("Sample Entry:", entries[0])
    
    if len(entries) == 0:
        print("FAILURE: No entries found. Selectors might be wrong.")
        
        # Debug: fetch raw to see HTML structure
        # (We can't easily see raw HTML output in this restricted shell, but we know if it failed)

if __name__ == "__main__":
    test()
