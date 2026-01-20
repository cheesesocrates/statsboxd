import cloudscraper
import datetime
import json
import os

class Scraper:
    def __init__(self, movies_path='movies.json'):
        self.movies_path = movies_path
        self.movies_db = self._load_movies_db()
        self.scraper = cloudscraper.create_scraper() # Create a CloudScraper instance

    def _load_movies_db(self):
        if os.path.exists(self.movies_path):
            with open(self.movies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def scrape_user(self, username):
        base_url = f"https://letterboxd.com/{username}/films/diary/"
        entries = []
        page = 1
        cutoff_date = datetime.date.today() - datetime.timedelta(days=365)
        
        while True:
            url = f"{base_url}page/{page}/"
            print(f"Scraping {url}...")
            try:
                response = self.scraper.get(url) # Use cloudscraper
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all('tr', class_='diary-entry-row')
                
                if not rows:
                    break

                page_entries = []
                for row in rows:
                    # Extract date
                    date_cell = row.find('td', class_='td-day')
                    if not date_cell: continue
                    
                    date_str = date_cell.find('a')['href'].split('/')[-2:] # roughly year/month/day link format checks might be needed or data-date
                    # Letterboxd diary date is usually in the format YYYY-MM-DD in the link or text
                    # Actually, let's look for the data-date attribute or the text in the link
                    # The link is usually /username/film/title/date/YYYY/MM/DD/
                    
                    # Safer way: extract from the text or other attributes
                    # The td-day usually has <a href="...">Day Date Month Year</a>
                    # But simpler is looking at the 'data-viewing-date' in the simplified format if present, or just parsing the link.
                    # Let's try parsing the partial link date from the <a href>
                    # Example href: /username/film/title/date/2024/01/20/
                    
                    link_href = date_cell.find('a')['href']
                    try:
                        parts = link_href.strip('/').split('/')
                        # parts expected: [username, 'film', title, 'date', year, month, day]
                        if 'date' in parts:
                            idx = parts.index('date')
                            if len(parts) >= idx + 3:
                                y, m, d = int(parts[idx+1]), int(parts[idx+2]), int(parts[idx+3])
                                watched_date = datetime.date(y, m, d)
                            else:
                                continue
                        else:
                            continue
                    except ValueError:
                        continue
                        
                    if watched_date < cutoff_date:
                        # We reached past 365 days
                        # finish this page but stop outer loop
                        # actually we can stop immediately if we want strictly last 365 days
                        return entries + page_entries

                    # Extract Title & Year
                    # The film title is in td-film-details -> h3 -> a
                    film_col = row.find('td', class_='td-film-details')
                    title_link = film_col.find('h3', class_='headline-3').find('a')
                    title = title_link.get_text(strip=True)
                    
                    # Year is often in metadata, but let's assume we might need to grab it from a separate span or just rely on DB match
                    # Letterboxd diary usually shows release year in the row? "td-released"
                    release_col = row.find('td', class_='td-released')
                    year = release_col.get_text(strip=True) if release_col else ""

                    # Extract Rating
                    rating_col = row.find('td', class_='td-rating')
                    rating = 0.0
                    if rating_col:
                        # Count stars or parsing text?
                        # Letterboxd uses unicode chars or classes "rating-5" etc.
                        # It often has a hidden text or class. 
                        # Class format: rating-5 (5 stars), rating-4 (4 stars), rating-3-5 (3.5 stars)
                        rating_span = rating_col.find('span', class_='rating')
                        if rating_span:
                            classes = rating_span.get('class', [])
                            for cls in classes:
                                if cls.startswith('rated-'):
                                    # rated-10 -> 5.0, rated-9 -> 4.5
                                    val = int(cls.split('-')[1])
                                    rating = val / 2.0
                                    break
                    
                    entry = {
                        "title": title,
                        "year": year,
                        "rating": rating,
                        "date": watched_date.strftime("%Y-%m-%d"),
                        "genre": self._infer_genre(title)
                    }
                    page_entries.append(entry)
                
                entries.extend(page_entries)
                page += 1
                
            except Exception as e:
                print(f"Error scraping page {page}: {e}")
                break
                
        return entries

    def _infer_genre(self, title):
        for movie in self.movies_db:
            if movie['title'].lower() == title.lower():
                return movie.get('genre', ['Uncategorized'])
        return ['Uncategorized']

if __name__ == "__main__":
    # Test
    s = Scraper()
    # print(s.scrape_user('somekeyuser'))
