#!/usr/bin/env python3
"""
Wikipedia Utilities
Shared utilities for searching and interacting with Wikipedia API
"""

import time
import logging
import requests
from bs4 import BeautifulSoup
import re
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class WikipediaSearcher:
    """Shared Wikipedia search functionality with caching"""
    
    def __init__(self, cache_dir='cache/wikipedia', cache_days=7, force_refresh=False):
        """
        Initialize Wikipedia searcher with caching support
        
        Args:
            cache_dir: Directory to store cached Wikipedia pages
            cache_days: Number of days before cache is considered stale
            force_refresh: If True, always fetch fresh data ignoring cache
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0
        
        # Cache configuration
        self.cache_dir = Path(cache_dir)
        self.cache_days = cache_days
        self.force_refresh = force_refresh
        
        # Create cache directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_cache_dir = self.cache_dir / 'searches'
        self.search_cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Wikipedia cache: {self.cache_dir} (expires after {cache_days} days, force_refresh={force_refresh})")
    
    def _get_cache_path(self, url):
        """
        Get the cache file path for a Wikipedia URL
        
        Args:
            url: Wikipedia URL
            
        Returns:
            Path object for the cache file
        """
        # Create a safe filename from the URL using hash
        url_hash = hashlib.md5(url.encode()).hexdigest()
        # Also include a human-readable part from the URL
        url_part = url.split('/')[-1][:50]  # Last part of URL, max 50 chars
        filename = f"{url_part}_{url_hash}.json"
        return self.cache_dir / filename
    
    def _get_search_cache_path(self, search_query):
        """
        Get the cache file path for a search query
        
        Args:
            search_query: Search query string
            
        Returns:
            Path object for the cache file
        """
        query_hash = hashlib.md5(search_query.encode()).hexdigest()
        safe_query = re.sub(r'[^a-zA-Z0-9_-]', '_', search_query.lower())[:50]
        filename = f"search_{safe_query}_{query_hash}.json"
        return self.search_cache_dir / filename
    
    def _is_cache_valid(self, cache_path):
        """
        Check if cache file exists and is not expired
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            bool: True if cache is valid and not expired
        """
        if not cache_path.exists():
            return False
        
        # Check file modification time
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        
        is_valid = age.days < self.cache_days
        if is_valid:
            logger.debug(f"Cache valid (age: {age.days} days): {cache_path.name}")
        else:
            logger.debug(f"Cache expired (age: {age.days} days): {cache_path.name}")
        
        return is_valid
    
    def _load_from_cache(self, url):
        """
        Load Wikipedia page content from cache
        
        Args:
            url: Wikipedia URL
            
        Returns:
            dict with 'html' and 'fetched_at', or None if not in cache
        """
        cache_path = self._get_cache_path(url)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                logger.debug(f"Loaded from cache: {url}")
                return cache_data
        except Exception as e:
            logger.warning(f"Failed to load cache file {cache_path}: {e}")
            return None
    
    def _save_to_cache(self, url, html_content):
        """
        Save Wikipedia page content to cache
        
        Args:
            url: Wikipedia URL
            html_content: HTML content to cache
        """
        cache_path = self._get_cache_path(url)
        
        try:
            cache_data = {
                'url': url,
                'html': html_content,
                'fetched_at': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved to cache: {url}")
        except Exception as e:
            logger.warning(f"Failed to save cache file {cache_path}: {e}")
    
    def _load_search_from_cache(self, search_query):
        """Load search results from cache"""
        cache_path = self._get_search_cache_path(search_query)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                logger.debug(f"Loaded search from cache: {search_query}")
                return cache_data.get('results')
        except Exception as e:
            logger.warning(f"Failed to load search cache: {e}")
            return None
    
    def _save_search_to_cache(self, search_query, search_results):
        """Save search results to cache"""
        cache_path = self._get_search_cache_path(search_query)
        
        try:
            cache_data = {
                'query': search_query,
                'results': search_results,
                'cached_at': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved search to cache: {search_query}")
        except Exception as e:
            logger.warning(f"Failed to save search cache: {e}")
    
    def _fetch_wikipedia_page(self, url):
        """
        Fetch Wikipedia page, using cache if available
        
        Args:
            url: Wikipedia URL to fetch
            
        Returns:
            HTML content as string, or None if fetch failed
        """
        # Check cache first (unless force_refresh is enabled)
        if not self.force_refresh:
            cached = self._load_from_cache(url)
            if cached:
                logger.info(f"  Using cached Wikipedia page (fetched: {cached['fetched_at'][:10]})")
                return cached['html']
        
        # Fetch from Wikipedia
        logger.info(f"  Fetching from Wikipedia...")
        self.rate_limit()
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Wikipedia returned status code {response.status_code}")
                return None
            
            # Save to cache
            self._save_to_cache(url, response.text)
            
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Wikipedia URL {url}: {e}")
            return None
    
    def rate_limit(self):
        """Enforce rate limiting for Wikipedia API"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def verify_wikipedia_reference(self, performer_name, wikipedia_url, context):
        """
        Verify that a Wikipedia URL is valid and refers to the correct performer
        
        Args:
            performer_name: Name of the performer
            wikipedia_url: Wikipedia URL to verify
            context: Dict with birth_date, death_date, sample_songs for verification
            
        Returns:
            Dict with 'valid' (bool), 'confidence' (str), 'reason' (str)
        """
        try:
            logger.debug(f"Verifying Wikipedia URL: {wikipedia_url}")
            
            # Fetch page (from cache if available)
            html_content = self._fetch_wikipedia_page(wikipedia_url)
            
            if not html_content:
                return {
                    'valid': False,
                    'confidence': 'certain',
                    'reason': 'Failed to fetch Wikipedia page'
                }
            
            # Parse the page
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get the main content area (skip navigation/menus)
            content_div = soup.find('div', {'id': 'mw-content-text'}) or soup.find('div', {'class': 'mw-parser-output'})
            if content_div:
                page_text = content_div.get_text().lower()
            else:
                page_text = soup.get_text().lower()
            
            # Check if this is a disambiguation or redirect to wrong page
            # Method 1: Check if page title explicitly ends with "(disambiguation)"
            page_title = soup.find('h1', {'id': 'firstHeading'})
            if page_title:
                page_title_text = page_title.get_text().strip()
                if page_title_text.endswith('(disambiguation)'):
                    logger.debug(f"Page title ends with '(disambiguation)' - rejecting page")
                    return {
                        'valid': False,
                        'confidence': 'high',
                        'reason': 'Page is a disambiguation page',
                        'score': 0
                    }
            
            # Method 1b: Check for actual disambiguation page indicators
            # Look for patterns like "may refer to" at the start, which indicates a real disambiguation page
            # Note: We ignore hatnotes like "For other uses, see X (disambiguation)" which just reference disambiguation pages
            logger.debug(f"Checking for disambiguation page indicators...")
            first_paragraph = page_text[:800]
            # Real disambiguation pages typically start with "[Name] may refer to:"
            if re.search(r'^[^.]*?\bmay refer to\b', first_paragraph):
                logger.debug(f"Found 'may refer to' pattern indicating disambiguation page")
                return {
                    'valid': False,
                    'confidence': 'high',
                    'reason': 'Page is a disambiguation page',
                    'score': 0
                }
            
            # Method 2: Check if page has many bullet points with birth/death dates
            # which suggests it's listing multiple people
            logger.debug(f"Checking for multiple birth year patterns...")
            ul_lists = soup.find_all('ul', limit=3)
            if ul_lists:
                list_text = ' '.join([ul.get_text() for ul in ul_lists[:2]])
                # Count how many birth year patterns like "(1942–2020)" or "(born 1974)"
                birth_patterns = re.findall(r'\((?:born\s+)?\d{4}', list_text)
                logger.debug(f"Found {len(birth_patterns)} birth year patterns: {birth_patterns[:5]}")
                if len(birth_patterns) >= 3:
                    logger.debug(f"Multiple birth patterns found - rejecting as disambiguation page")
                    return {
                        'valid': False,
                        'confidence': 'high',
                        'reason': f'Page appears to be a disambiguation page (lists {len(birth_patterns)} different people)',
                        'score': 0
                    }
            
            # Calculate confidence based on multiple factors
            confidence_score = 0
            reasons = []
            
            # Check name similarity
            page_title = soup.find('h1', {'id': 'firstHeading'})
            if page_title:
                page_title_text = page_title.get_text().strip()
                
                # Check if the title disambiguation clearly indicates a NON-musician
                # Extract the disambiguation term in parentheses (e.g., "(basketball)" from "Sam Jones (basketball)")
                disambiguation_match = re.search(r'\(([^)]+)\)$', page_title_text)
                if disambiguation_match:
                    disambiguation_term = disambiguation_match.group(1).lower()
                    
                    # Non-musician professions/fields
                    non_musician_terms = [
                        'basketball', 'football', 'baseball', 'hockey', 'soccer', 'cricket',
                        'athlete', 'sports', 'player', 'coach',
                        'politician', 'politics', 'senator', 'congressman', 'mayor',
                        'businessman', 'business', 'entrepreneur', 'ceo', 'executive',
                        'actor', 'actress', 'film', 'television',
                        'writer', 'author', 'journalist', 'poet',
                        'scientist', 'physicist', 'chemist', 'biologist',
                        'military', 'general', 'admiral', 'colonel'
                    ]
                    
                    # Musician-related terms that should NOT reject
                    musician_terms = [
                        'musician', 'singer', 'vocalist', 'pianist', 'guitarist', 'bassist',
                        'drummer', 'saxophonist', 'trumpeter', 'composer', 'conductor',
                        'bandleader', 'jazz', 'blues', 'rock', 'folk', 'country'
                    ]
                    
                    # Check if disambiguation term indicates non-musician
                    is_non_musician = any(term in disambiguation_term for term in non_musician_terms)
                    is_musician = any(term in disambiguation_term for term in musician_terms)
                    
                    if is_non_musician and not is_musician:
                        logger.debug(f"Page title indicates non-musician: '{page_title_text}'")
                        return {
                            'valid': False,
                            'confidence': 'high',
                            'reason': f'Page is about a {disambiguation_term}, not a musician',
                            'score': 0
                        }
                
                # Remove disambiguation parentheses like "(saxophonist)"
                page_name = re.sub(r'\s*\([^)]*\)\s*$', '', page_title_text).strip().lower()
                performer_name_lower = performer_name.lower()
                
                name_match = False
                if page_name == performer_name_lower:
                    confidence_score += 30
                    reasons.append(f"Exact name match")
                    name_match = True
                elif performer_name_lower in page_name or page_name in performer_name_lower:
                    confidence_score += 15
                    reasons.append(f"Partial name match")
                    name_match = True
                else:
                    # Name doesn't match - this is suspicious
                    reasons.append(f"Name mismatch: expected '{performer_name}', page is '{page_title_text}'")
            
            # Look for infobox (strong signal this is a musician page)
            infobox = soup.find('table', {'class': 'infobox'})
            if infobox:
                infobox_text = infobox.get_text().lower()
                
                # Check for SPECIFIC music-related terms in infobox (not just "occupation")
                specific_music_terms = [
                    'jazz', 'musician', 'singer', 'vocalist', 'pianist', 'composer',
                    'saxophonist', 'trumpeter', 'bassist', 'drummer', 'guitarist',
                    'bandleader', 'blues', 'soul', 'r&b', 'gospel', 'folk',
                    'instruments', 'genres', 'labels'
                ]
                found_specific_terms = [term for term in specific_music_terms if self._word_in_text(term, infobox_text)]
                if found_specific_terms:
                    confidence_score += 40  # Strong signal
                    reasons.append(f"Infobox contains music terms: {', '.join(found_specific_terms[:3])}")
                elif 'occupation' in infobox_text:
                    # Has occupation but no music-specific terms - only give small boost
                    confidence_score += 10
                    reasons.append(f"Infobox present but no specific music terms")
            
            # Check for jazz musician keywords in main content
            # Use more specific terms that are clearly music-related
            specific_music_keywords = [
                'jazz', 'musician', 'singer', 'vocalist', 'pianist', 
                'saxophonist', 'trumpeter', 'bassist', 'drummer', 
                'guitarist', 'composer', 'bandleader',
                'album', 'recording', 'blues', 'soul', 'r&b', 
                'gospel', 'folk', 'orchestra', 'symphony',
                'concerto', 'sonata', 'opera'
            ]
            # More generic terms that need context (could be sports, business, etc)
            generic_music_keywords = [
                'music', 'song', 'performance', 'concert', 'stage'
            ]
            
            # Search in first 2000 characters using word boundary matching
            # FIXED: Use word boundaries to avoid matching "opera" in "operating"
            found_specific = [kw for kw in specific_music_keywords if self._word_in_text(kw, page_text[:2000])]
            found_generic = [kw for kw in generic_music_keywords if self._word_in_text(kw, page_text[:2000])]
            
            if found_specific:
                # Specific music terms get full points
                confidence_score += 20
                reasons.append(f"Found music keywords: {', '.join(found_specific[:3])}")
            elif found_generic:
                # Generic terms only get partial credit and only if we have other signals
                confidence_score += 5
                reasons.append(f"Found generic music keywords: {', '.join(found_generic[:2])}")
            
            # Check birth/death dates if available
            if context.get('birth_date'):
                birth_year = str(context['birth_date'].year) if hasattr(context['birth_date'], 'year') else str(context['birth_date'])[:4]
                if birth_year in page_text[:2000]:
                    confidence_score += 25
                    reasons.append(f"Birth year {birth_year} found on page")
            
            if context.get('death_date'):
                death_year = str(context['death_date'].year) if hasattr(context['death_date'], 'year') else str(context['death_date'])[:4]
                if death_year in page_text[:2000]:
                    confidence_score += 20
                    reasons.append(f"Death year {death_year} found on page")
            
            # Check if any of the performer's songs are mentioned
            if context.get('sample_songs'):
                song_mentions = [song for song in context['sample_songs'] 
                               if song and song.lower() in page_text]
                if song_mentions:
                    confidence_score += 25
                    reasons.append(f"Found song references: {', '.join(song_mentions[:2])}")
            
            # Determine validity based on confidence score
            # Require at least 50 points (medium confidence) to accept
            if confidence_score >= 50:
                return {
                    'valid': True,
                    'confidence': 'high' if confidence_score >= 70 else 'medium',
                    'reason': '; '.join(reasons) if reasons else 'Page appears valid (score: {})'.format(confidence_score),
                    'score': confidence_score
                }
            else:
                return {
                    'valid': False,
                    'confidence': 'low' if confidence_score >= 30 else 'very_low',
                    'reason': 'Insufficient evidence of correct performer (score: {}): {}'.format(confidence_score, '; '.join(reasons)),
                    'score': confidence_score
                }
                
        except requests.RequestException as e:
            logger.error(f"Error verifying Wikipedia URL {wikipedia_url}: {e}")
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying Wikipedia: {e}", exc_info=True)
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Verification error: {str(e)}'
            }
    
    def _word_in_text(self, word, text):
        """
        Check if a word exists in text as a complete word (not as part of another word)
        
        Args:
            word: The word to search for (case-insensitive)
            text: The text to search in (should already be lowercased)
            
        Returns:
            bool: True if word is found as a complete word
        """
        # Use word boundary regex to match only complete words
        # \b ensures we match whole words only
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        return bool(re.search(pattern, text.lower()))


    def search_wikipedia(self, performer_name, context):
        """
        Search Wikipedia for a performer
        
        Args:
            performer_name: Name to search for
            context: Dict with additional info for verification
            
        Returns:
            Wikipedia URL if found with reasonable confidence, None otherwise
        """
        try:
            # Check cache first (unless force_refresh is enabled)
            if not self.force_refresh:
                cached_results = self._load_search_from_cache(performer_name)
                if cached_results:
                    logger.info(f"  Using cached search results")
                    urls = cached_results
                else:
                    # Perform API search
                    search_url = "https://en.wikipedia.org/w/api.php"
                    params = {
                        'action': 'opensearch',
                        'search': performer_name,
                        'limit': 5,
                        'namespace': 0,
                        'format': 'json'
                    }
                    
                    self.rate_limit()
                    response = self.session.get(search_url, params=params, timeout=10)
                    
                    if response.status_code != 200:
                        return None
                    
                    data = response.json()
                    if len(data) < 4 or not data[3]:
                        return None
                    
                    urls = data[3]
                    
                    # Save to cache
                    self._save_search_to_cache(performer_name, urls)
            else:
                # Force refresh - skip cache
                search_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    'action': 'opensearch',
                    'search': performer_name,
                    'limit': 5,
                    'namespace': 0,
                    'format': 'json'
                }
                
                self.rate_limit()
                response = self.session.get(search_url, params=params, timeout=10)
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                if len(data) < 4 or not data[3]:
                    return None
                
                urls = data[3]

            # Verify each URL until we find a good match
            for url in urls[:5]:
                verification = self.verify_wikipedia_reference(performer_name, url, context)
                logger.info(f"  Checked {url}: valid={verification['valid']}, confidence={verification['confidence']}, score={verification.get('score', 0)}, reason={verification['reason']}")
                if verification['valid']:
                    logger.info(f"  Found Wikipedia: {url} (confidence: {verification['confidence']}, score: {verification.get('score', 0)})")
                    logger.info(f"    Reason: {verification['reason']}")
                    return url
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching Wikipedia for {performer_name}: {e}")
            return None