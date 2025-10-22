#!/usr/bin/env python3
"""
MusicBrainz Utilities
Shared utilities for searching and interacting with MusicBrainz API
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)


class MusicBrainzSearcher:
    """Shared MusicBrainz search functionality"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # MusicBrainz requires 1 second between requests
    
    def rate_limit(self):
        """Enforce rate limiting for MusicBrainz API"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def normalize_title(self, title):
        """
        Normalize title for comparison by handling various punctuation differences
        
        Args:
            title: Title to normalize
        
        Returns:
            Normalized title string
        """
        normalized = title.lower()
        
        # Replace all types of apostrophes with standard apostrophe
        # Includes: ' (right single quotation), ʼ (modifier letter apostrophe), 
        # ` (grave accent), ´ (acute accent)
        apostrophe_variants = [''', ''', 'ʼ', '`', '´']
        for variant in apostrophe_variants:
            normalized = normalized.replace(variant, "'")
        
        # Replace different types of dashes/hyphens
        dash_variants = ['–', '—', '−']  # en dash, em dash, minus
        for variant in dash_variants:
            normalized = normalized.replace(variant, '-')
        
        # Replace different types of quotes
        quote_variants = ['"', '"', '„', '«', '»']  # smart quotes, guillemets
        for variant in quote_variants:
            normalized = normalized.replace(variant, '"')
        
        return normalized
    
    def search_musicbrainz_work(self, title, composer):
        """
        Search MusicBrainz for a work by title and composer
        
        Args:
            title: Song title
            composer: Composer name(s)
        
        Returns:
            MusicBrainz Work ID if found, None otherwise
        """
        self.rate_limit()
        
        # Build search query
        # Search by title and optionally composer
        query_parts = [f'work:"{title}"']
        
        if composer:
            # Extract first composer if multiple
            first_composer = composer.split(',')[0].split(' and ')[0].strip()
            query_parts.append(f'artist:"{first_composer}"')
        
        query = ' AND '.join(query_parts)
        
        logger.debug(f"    Searching MusicBrainz: {query}")
        
        try:
            response = self.session.get(
                'https://musicbrainz.org/ws/2/work/',
                params={
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            works = data.get('works', [])
            
            if not works:
                logger.debug(f"    ✗ No MusicBrainz works found")
                return None
            
            # Normalize search title for comparison
            normalized_search_title = self.normalize_title(title)
            
            # Look for exact or very close title match
            for work in works:
                work_title = work.get('title', '')
                normalized_work_title = self.normalize_title(work_title)
                
                # Check for exact match after normalization
                if normalized_work_title == normalized_search_title:
                    mb_id = work['id']
                    logger.debug(f"    ✓ Found: '{work['title']}' (ID: {mb_id})")
                    
                    # Show composer if available
                    if 'artist-relation-list' in work:
                        composers = [r['artist']['name'] for r in work['artist-relation-list'] 
                                   if r['type'] == 'composer']
                        if composers:
                            logger.debug(f"       Composer(s): {', '.join(composers)}")
                    
                    return mb_id
            
            # If no exact match, show what was found
            logger.debug(f"    ⚠ Found {len(works)} works but no exact match:")
            for work in works[:3]:
                logger.debug(f"       - '{work['title']}'")
            
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"    ⚠ MusicBrainz search timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"    ✗ MusicBrainz search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"    ✗ Error searching MusicBrainz: {e}")
            return None