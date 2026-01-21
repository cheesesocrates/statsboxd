import cloudscraper
from bs4 import BeautifulSoup
import datetime
import json
import os
import logging

class Scraper:
    def __init__(self, movies_path='movies.json'):
        self.movies_path = movies_path
        self.movies_db = self._load_movies_db()
        # Attempt to mimic a real desktop browser to bypass Cloudflare on Vercel
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def _load_movies_db(self):
        if os.path.exists(self.movies_path):
            with open(self.movies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def scrape_page(self, username, page):
        logging.info(f"Starting scrape for user: {username}, Page: {page}")
        base_url = f"https://letterboxd.com/{username}/films/diary/"
        entries = []
        has_next = False
        
        url = f"{base_url}page/{page}/"
        logging.info(f"Scraping page {page}: {url}...")
        
        try:
            response = self.scraper.get(url) 
            logging.info(f"Response Status: {response.status_code}, Length: {len(response.text)}")
            
            # 404 usually means page doesn't exist (past the end)
            if response.status_code == 404:
                return {"entries": [], "has_next": False}
                
            if response.status_code != 200:
                logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")
                return {"entries": [], "has_next": False}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr', class_='diary-entry-row')
            
            if not rows:
                return {"entries": [], "has_next": False}
            
            # Check for "Next" button in pagination
            # Class .paginate-next or next link
            next_link = soup.find('a', class_='next') 
            has_next = True if next_link else False
            
            # Double check: if 50 rows, maybe next? 
            # Letterboxd pagination usually exact.
            
            for row in rows:
                # Extract date
                date_cell = row.find('td', class_='col-daydate')
                if not date_cell: continue
                
                date_link = date_cell.find('a')
                if not date_link: continue
                
                link_href = date_link['href']
                
                try:
                    parts = link_href.strip('/').split('/')
                    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit() and parts[-3].isdigit():
                        y, m, d = int(parts[-3]), int(parts[-2]), int(parts[-1])
                        watched_date = datetime.date(y, m, d)
                    else:
                        continue
                except ValueError:
                    continue
                    
                # Extract Title
                film_col = row.find('td', class_='col-production')
                title = "Unknown"
                if film_col:
                    title_header = film_col.find(class_='name')
                    if title_header:
                        title_link = title_header.find('a')
                        if title_link:
                            title = title_link.get_text(strip=True)
                
                # Extract Year
                release_col = row.find('td', class_='col-releaseyear')
                year = release_col.get_text(strip=True) if release_col else ""

                # Extract Rating
                rating_col = row.find('td', class_='col-rating')
                rating = 0.0
                if rating_col:
                    rating_span = rating_col.find('span', class_='rating')
                    if rating_span:
                        classes = rating_span.get('class', [])
                        for cls in classes:
                            if cls.startswith('rated-'):
                                try:
                                    val = int(cls.split('-')[1])
                                    rating = val / 2.0
                                except:
                                    pass
                                break
                
                entry = {
                    "title": title,
                    "year": year,
                    "rating": rating,
                    "date": watched_date.strftime("%Y-%m-%d"),
                    "genre": self._infer_genre(title)
                }
                entries.append(entry)
            
            logging.info(f"Page {page}: Scraped {len(entries)} entries. Has Next: {has_next}")
            
        except Exception as e:
            logging.error(f"Error scraping page {page}: {e}")
            return {"entries": [], "has_next": False}
            
        return {"entries": entries, "has_next": has_next}

    def _infer_genre(self, title):
        for movie in self.movies_db:
            if movie['title'].lower() == title.lower():
                return movie.get('genre', ['Uncategorized'])
        return ['Uncategorized']

if __name__ == "__main__":
    # Test
    s = Scraper()
    # print(s.scrape_user('somekeyuser'))
