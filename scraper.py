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
                    # Normalize parts to find date components
                    # Expected: .../YYYY/MM/DD/ or .../YYYY/MM/ or .../YYYY/
                    # Find year (4 digits)
                    y, m, d = None, 1, 1
                    
                    found_year_idx = -1
                    for i in range(len(parts)-1, -1, -1):
                        if parts[i].isdigit() and len(parts[i]) == 4:
                            y = int(parts[i])
                            found_year_idx = i
                            break
                    
                    if y:
                        # Try to find month/day after year
                        if found_year_idx + 1 < len(parts) and parts[found_year_idx+1].isdigit():
                            m = int(parts[found_year_idx+1])
                            if found_year_idx + 2 < len(parts) and parts[found_year_idx+2].isdigit():
                                d = int(parts[found_year_idx+2])
                        
                        watched_date = datetime.date(y, m, d)
                    else:
                        watched_date = None
                except ValueError:
                     watched_date = None
                
                # If date parsing failed, don't skip! Add as Undated.
                if not watched_date:
                     # Attempt fallback from text? "Jan 01" -> hard without Year context.
                     # Just assume None
                     pass
                    
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

    def scrape_films_page(self, username, page):
        """
        Scrapes the 'Films' page (All watched films, including undated).
        URL: /username/films/page/X/
        """
        logging.info(f"Starting FILMS scrape for user: {username}, Page: {page}")
        
        if page == 1:
            url = f"https://letterboxd.com/{username}/films/"
        else:
            url = f"https://letterboxd.com/{username}/films/page/{page}/"
            
        entries = []
        has_next = False
        
        try:
            response = self.scraper.get(url)
            logging.info(f"Response Status: {response.status_code}")
            
            # Check 404 (End of pages)
            if response.status_code == 404:
                return {"entries": [], "has_next": False}

            soup = BeautifulSoup(response.text, 'html.parser')
            logging.info(f"Page Title: {soup.title.string if soup.title else 'No Title'}")
            
            # Pagination check
            next_link = soup.find('a', class_='next')
            has_next = True if next_link else False
            
            # Selectors
            # Try Grid View (li.griditem) - Common in /films/
            posters = soup.select('li.griditem')
            
            # Fallback to List View (li.poster-container)
            if not posters:
                logging.info("No .griditem found. Trying .poster-container.")
                posters = soup.select('li.poster-container')

            if not posters:
                logging.info("No posters found. Trying .poster-list li.")
                posters = soup.select('.poster-list li')
            
            logging.info(f"Found {len(posters)} poster containers.")
            
            for li in posters:
                # 1. Try data-item-name (Common in React grids/LazyPoster)
                div = li.find('div', attrs={'data-item-name': True})
                
                # 2. Try data-film-name (Older/List views)
                if not div:
                    div = li.find('div', attrs={'data-film-name': True})
                
                # 3. Fallback try class
                if not div:
                    div = li.find('div', class_='film-poster')
                
                # 4. Fallback to Image
                
                title = "Unknown"
                year = ""
                
                if div:
                    title = div.get('data-item-name') or div.get('data-film-name') or "Unknown"
                    year = div.get('data-film-release-year', '')
                else:
                    # Fallback to Image
                    img = li.find('img')
                    if img:
                        title = img.get('alt', 'Unknown')
                
                if title == "Unknown": continue

                # Clean title if it includes year (e.g. "Name (2024)")
                if title and title.endswith(')') and '(' in title:
                     try:
                         # Last part might be (YYYY)
                         # Simple check
                         parts = title.rsplit('(', 1)
                         if len(parts) == 2:
                             possible_year = parts[1].rstrip(')')
                             if possible_year.isdigit() and len(possible_year) == 4:
                                 title = parts[0].strip()
                                 if not year: year = possible_year
                     except: pass

                # Rating
                rating = 0.0
                try:
                    # In film grid, rating is hidden or in a specific span
                    # Usually .poster-viewingdata > .rating
                    viewing_data = li.find('p', class_='poster-viewingdata')
                    if viewing_data:
                         rating_span = viewing_data.find('span', class_='rating')
                         if rating_span:
                             classes = rating_span.get('class', [])
                             for cls in classes:
                                 if cls.startswith('rated-'):
                                     rating = int(cls.split('-')[1]) / 2.0
                                     break
                except:
                    pass
                
                entry = {
                    "title": title,
                    "year": year,
                    "rating": rating,
                    "date": None, # Undated
                    "genre": self._infer_genre(title)
                }
                entries.append(entry)
                
            logging.info(f"Page {page} (Films): Scraped {len(entries)} entries.")
            
        except Exception as e:
            logging.error(f"CRITICAL ERROR scraping films page {page}: {e}")
            import traceback
            # traceback.print_exc()
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
