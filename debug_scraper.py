import cloudscraper

def test_cloudscraper():
    scraper = cloudscraper.create_scraper()
    url = "https://letterboxd.com/davidehrlich/films/diary/page/1/"
    try:
        print(f"Attempting to scrape {url} with cloudscraper...")
        response = scraper.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! First 200 chars:")
            print(response.text[:200])
        else:
            print("Blocked.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_cloudscraper()
