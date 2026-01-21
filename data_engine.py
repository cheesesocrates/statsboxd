import os
import json
import random
import logging
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

class DataEngine:
    def __init__(self, movies_path='movies.json'):
        self.movies_path = movies_path
        self.movies_db = self._load_movies_db()
        self.tmdb_key = os.getenv("TMDB_API_KEY")
        self.mode = "LIVE" if self.tmdb_key else "OFFLINE"
        logging.info(f"DataEngine initialized in {self.mode} mode.")

    def _load_movies_db(self):
        if os.path.exists(self.movies_path):
            with open(self.movies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def get_quiz_question(self, watched_movies=None):
        """
        Returns a dictionary:
        {
            "question": str,
            "options": [str, str, str, str],
            "correct_index": int,
            "movie_title": str,
            "poster_url": str
        }
        """
        # Always use the Rating Quiz logic
        return self._get_rating_quiz(watched_movies)

    def _get_rating_quiz(self, watched_movies):
        target_movie = None
        
        if watched_movies and len(watched_movies) > 0:
            target_movie = random.choice(watched_movies)
            user_rating = target_movie['rating']
        else:
            # If no watched data, pick random from DB and pretend
            target_movie = random.choice(self.movies_db)
            user_rating = random.choice([3.0, 3.5, 4.0, 4.5, 5.0]) # Mock rating
            target_movie['rating'] = user_rating

        # Try to get real poster if TMDB key exists
        poster_url = self._get_tmdb_poster(target_movie['title'])
        
        # If TMDB failed or no key, check local DB for fallback
        if "via.placeholder.com" in poster_url:
             db_match = next((m for m in self.movies_db if m['title'].lower() == target_movie['title'].lower()), None)
             if db_match:
                 poster_url = db_match['poster_url']

        question = f"You watched '{target_movie['title']}'. What star rating did you give it?"
        
        # Generate options
        correct_rating = float(target_movie['rating'])
        options = [correct_rating]
        while len(options) < 4:
            # Generate random rating between 0.5 and 5.0 in 0.5 steps
            r = random.randint(1, 10) / 2.0
            if r not in options:
                options.append(r)
        
        random.shuffle(options)
        
        return {
            "question": question,
            "options": [f"{opt} stars" for opt in options],
            "correct_index": options.index(correct_rating),
            "movie_title": target_movie['title'],
            "poster_url": poster_url
        }

    def _get_tmdb_poster(self, title):
        if not self.tmdb_key:
            return "https://via.placeholder.com/300x450?text=No+Poster"
            
        from tmdbv3api import TMDb, Movie
        tmdb = TMDb()
        tmdb.api_key = self.tmdb_key
        movie_api = Movie()
        
        try:
            search = movie_api.search(title)
            if search:
                # Get first result
                path = search[0].poster_path
                if path:
                    return f"https://image.tmdb.org/t/p/w500{path}"
        except Exception as e:
            print(f"TMDB Error for {title}: {e}")
            pass
        
        return "https://via.placeholder.com/300x450?text=No+Poster"

    def _hydrate_with_tmdb(self, movies):
        """
        Updates the passed list of movies in-place with Genres and Poster URLs from TMDB.
        Uses ThreadPoolExecutor for speed.
        """
        if not self.tmdb_key: 
            return
        
        from tmdbv3api import TMDb, Movie, Genre
        import concurrent.futures
        
        tmdb = TMDb()
        tmdb.api_key = self.tmdb_key
        # Note: tmdbv3api might not be fully thread-safe if sharing objects?
        # Provide thread-local instances if needed, but usually http requests are fine.
        
        # Pre-fetch genre map (fast, single call)
        try:
            genre_api = Genre()
            genres_list = genre_api.movie_list()
            if isinstance(genres_list, list):
                genre_map = {g['id']: g['name'] for g in genres_list}
            elif hasattr(genres_list, 'genres'):
                 genre_map = {g['id']: g['name'] for g in genres_list.genres}
            else:
                 genre_map = {}
        except Exception as e:
            logging.error(f"Failed to fetch genre map: {e}")
            genre_map = {}

        logging.info("Hydrating movies with TMDB data (Parallel)...")
        
        # Identify movies needing hydration
        to_hydrate = [m for m in movies if m.get('genre') == ['Uncategorized'] or not m.get('poster_url')]
        
        if not to_hydrate:
            return

        def process_movie(movie):
            try:
                # Create local instance per thread just in case
                local_movie_api = Movie()
                results = local_movie_api.search(movie['title'])
                target_year = movie['year']
                match = None
                
                if results:
                    if target_year:
                        for r in results:
                            if hasattr(r, 'release_date') and str(target_year) in r.release_date:
                                match = r
                                break
                    if not match: match = results[0]
                    
                    if match:
                         if hasattr(match, 'poster_path') and match.poster_path:
                             movie['poster_url'] = f"https://image.tmdb.org/t/p/w500{match.poster_path}"
                         if hasattr(match, 'release_date') and match.release_date:
                             movie['release_date'] = match.release_date
                         if hasattr(match, 'genre_ids') and genre_map:
                             real_genres = [genre_map.get(gid) for gid in match.genre_ids if gid in genre_map]
                             if real_genres:
                                 movie['genre'] = real_genres
            except:
                pass

        # Run in parallel to speed up (Increased workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            executor.map(process_movie, to_hydrate)
            
        logging.info(f"Hydration complete for {len(to_hydrate)} movies.")


    def analyze_profile(self, watched_movies, year=None, include_undated=False):
        """
        Analyzes statistics and hydrates data. 
        """
        grand_total = len(watched_movies) if watched_movies else 0
        undated_count = sum(1 for m in watched_movies if not m.get('date'))
        
        logging.info(f"Analyzing profile. Total: {grand_total}. Undated: {undated_count}. Year: {year}. Include Undamed: {include_undated}")
        
        if not watched_movies:
            return {
                "total_films": 0,
                "grand_total": 0,
                "undated_count": 0,
                "average_rating": 0,
                "top_genres": [],
                "heatmap_data": {}
            }
            
        if self.tmdb_key:
            self._hydrate_with_tmdb(watched_movies)
            
        # Filter by year if requested
        # SPECIAL LOGIC: If include_undated is True, we might need to include undated films 
        # that "fall into" this year based on release_date
        target_movies = []
        for m in watched_movies:
            d = m.get('date')
            
            # If no date, try fallback
            if not d and include_undated and m.get('release_date'):
               d = m['release_date']
            
            # If still no date, strict filter skips it unless we are not filtering by year
            if year:
                if d and d.startswith(str(year)):
                    target_movies.append(m)
            else:
                target_movies.append(m) # All time

        total_films = len(target_movies)
        total_rating = sum(m['rating'] for m in target_movies)
        average_rating = round(total_rating / total_films, 2) if total_films > 0 else 0
        
        # Genre Analysis (Weighted by count)
        genre_counts = {}
        for m in target_movies:
            for g in m.get('genre', []):
                if g == 'Uncategorized' and len(m.get('genre', [])) > 1: continue
                genre_counts[g] = genre_counts.get(g, 0) + 1
        
        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        
        logging.info(f"Analysis done for {year if year else 'ALL'}. Films: {total_films}")
        
        # Heatmap Data (Enriched for Hover)
        heatmap_data = {}
        
        for m in target_movies:
            # Determine date for heatmap placement
            d = m.get('date')
            if not d:
                if include_undated and m.get('release_date'):
                    d = m['release_date']
                else:
                    continue # Skip if really no date
                
            if d not in heatmap_data:
                heatmap_data[d] = {'count': 0, 'movies': []}
            
            heatmap_data[d]['count'] += 1
            # Add title
            heatmap_data[d]['movies'].append(m['title'])
            
        return {
            "total_films": total_films,
            "grand_total": grand_total,
            "undated_count": undated_count,
            "average_rating": average_rating,
            "top_genres": sorted_genres,
            "heatmap_data": heatmap_data,
            "year": year
        }

    def get_genre_evolution(self, watched_movies, year_filter=None):
        """
        Returns evolution data.
        If year_filter is None: { "2023": { "Action": 5, ... }, ... }
        If year_filter is "2024": { "Jan": { "Action": 1... }, "Feb": ... }
        """
        evolution = {}
        
        # Helper for Month Names
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        target_movies = watched_movies
        if year_filter:
            target_movies = [m for m in watched_movies if m['date'].startswith(str(year_filter))]
            
            # Initialize all months to ensure continuity
            for m in month_names:
                evolution[m] = {}
        
        for m in target_movies:
            if not m.get('date'): continue
            
            date_parts = m['date'].split('-') # YYYY-MM-DD
            y = date_parts[0]
            month_idx = int(date_parts[1]) - 1
            
            key = y # Default key is Year
            if year_filter:
                key = month_names[month_idx]
            
            if key not in evolution: evolution[key] = {}
            
            for g in m.get('genre', []):
                if g == 'Uncategorized': continue
                evolution[key][g] = evolution[key].get(g, 0) + 1
        
        return evolution

    def get_recommendations(self, watched_movies):
        """
        Get recommendations based on STARTLINGLY RECENT taste (Last 25 movies).
        But exclude ALL watched movies.
        """
        import re
        def normalize(t): return re.sub(r'[^a-z0-9]', '', t.lower())
        
        if not watched_movies: return []
            
        # 1. Exclusion Set (All watched)
        watched_titles = set(normalize(m['title']) for m in watched_movies)
        
        # 2. Taste Source (First 25, assuming movies[0] is latest)
        # Note: Scraper usually appends? Wait.
        # Scraper fetches Page 1, then Page 2...
        # Page 1 contains [Newest ... Older].
        # So index 0 is indeed Newest.
        recent_batch = watched_movies[:25]
        
        # 3. Calculate Top Genres from Recent Batch
        genre_counts = {}
        for m in recent_batch:
            for g in m.get('genre', []):
                if g == 'Uncategorized': continue
                genre_counts[g] = genre_counts.get(g, 0) + 1
        
        # Sort and take top 3-5
        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        top_genres_names = set(g[0] for g in sorted_genres[:5])
        
        rec_candidates = []
        
        for movie in self.movies_db:
             if normalize(movie['title']) in watched_titles:
                continue
             
             movie_genres = set(movie.get('genre', []))
             
             if not top_genres_names:
                 # Random fallback if no genre info
                 rec_candidates.append(movie)
                 continue
                 
             # Check intersection
             if movie_genres.intersection(top_genres_names):
                 rec_candidates.append(movie)
        
        random.shuffle(rec_candidates)
        selected = rec_candidates[:10]
        
        final_recs = []
        for m in selected:
            tmdb_poster = self._get_tmdb_poster(m['title'])
            final_recs.append({
                "title": m['title'],
                "year": m['year'],
                "poster_url": tmdb_poster if "via.placeholder.com" not in tmdb_poster else m['poster_url']
            })
            
        return final_recs
