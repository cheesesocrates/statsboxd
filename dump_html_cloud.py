import cloudscraper

def dump_html_cloud():
    scraper = cloudscraper.create_scraper()
    url = "https://letterboxd.com/davidehrlich/films/diary/page/1/"
    try:
        print(f"Fetching {url}...")
        response = scraper.get(url)
        print(f"Status: {response.status_code}")
        with open("debug_cloudscraper.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Saved debug_cloudscraper.html")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_html_cloud()
