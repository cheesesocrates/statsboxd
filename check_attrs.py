import cloudscraper
from bs4 import BeautifulSoup
import logging

def check_attrs():
    user = "cheesesocrates"
    url = f"https://letterboxd.com/{user}/films/diary/"
    scraper = cloudscraper.create_scraper()
    res = scraper.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    rows = soup.find_all('tr', class_='diary-entry-row')
    
    print(f"Found {len(rows)} rows.")
    for i, row in enumerate(rows[:5]):
        print(f"Row {i} attributes: {row.attrs}")
        # Check specific children attributes too just in case
        day_cell = row.find('td', class_='col-daydate')
        if day_cell:
            print(f"  Date Cell: {day_cell.get_text(strip=True)}")

if __name__ == "__main__":
    check_attrs()
