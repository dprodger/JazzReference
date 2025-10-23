#!/usr/bin/env python3
"""
Verify Performer External References
Reviews all performers in the database and validates/updates Wikipedia and MusicBrainz references
"""

import sys
import argparse
import logging
import json
import time
import re
from datetime import datetime

# Third-party imports
import requests
from bs4 import BeautifulSoup

# Local imports - adjust path as needed
try:
    from db_utils import get_db_connection
except ImportError:
    print("Error: db_utils.py must be in the same directory or Python path")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/verify_performer_references.log')
    ]
)
logger = logging.getLogger(__name__)


class PerformerReferenceVerifier:
    """Verify and update external references for performers"""
    
    def __init__(self, dry_run=False, name_filter=None, id_filter=None, reftype_filter=None):
        """
        Initialize verifier
        
        Args:
            dry_run: If True, show what would be done without making changes
            name_filter: If provided, only process performer with this name
            id_filter: If provided, only process performer with this UUID
            reftype_filter: If provided, only check this reference type ('wikipedia' or 'musicbrainz')
        """
        self.dry_run = dry_run
        self.name_filter = name_filter
        self.id_filter = id_filter
        self.reftype_filter = reftype_filter
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (Educational)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
        self.stats = {
            'performers_processed': 0,
            'valid_references': 0,
            'invalid_references': 0,
            'missing_references': 0,
            'references_added': 0,
            'errors': 0
        }
    
    def get_performers(self):
        """Get all performers from database with their recordings for context"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build query with optional filters
                query = """
                    SELECT 
                        p.id,
                        p.name,
                        p.external_links,
                        p.birth_date,
                        p.death_date,
                        p.biography,
                        -- Get some sample recordings for verification
                        ARRAY_AGG(DISTINCT s.title) FILTER (WHERE s.title IS NOT NULL) as sample_songs
                    FROM performers p
                    LEFT JOIN recording_performers rp ON p.id = rp.performer_id
                    LEFT JOIN recordings r ON rp.recording_id = r.id
                    LEFT JOIN songs s ON r.song_id = s.id
                """
                
                params = []
                where_clauses = []
                
                # Add name filter if specified
                if self.name_filter:
                    where_clauses.append("LOWER(p.name) = LOWER(%s)")
                    params.append(self.name_filter)
                
                # Add id filter if specified
                if self.id_filter:
                    where_clauses.append("p.id = %s")
                    params.append(self.id_filter)
                
                # Add WHERE clause if we have filters
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                query += """
                    GROUP BY p.id, p.name, p.external_links, p.birth_date, p.death_date, p.biography
                    ORDER BY p.name
                """
                
                cur.execute(query, tuple(params))
                return cur.fetchall()
    
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
            
            # Check if URL is reachable
            response = self.session.get(wikipedia_url, timeout=10)
            time.sleep(1.0)  # Rate limiting
            
            if response.status_code != 200:
                return {
                    'valid': False,
                    'confidence': 'certain',
                    'reason': f'URL returned status code {response.status_code}'
                }
            
            # Parse the page
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text().lower()
            
            # Check if this is a disambiguation or redirect to wrong page
            if 'disambiguation' in page_text[:500]:
                return {
                    'valid': False,
                    'confidence': 'high',
                    'reason': 'Page is a disambiguation page'
                }
            
            # Calculate confidence based on multiple factors
            confidence_score = 0
            reasons = []
            
            # Look for infobox (strong signal this is a musician page)
            infobox = soup.find('table', {'class': 'infobox'})
            if infobox:
                infobox_text = infobox.get_text().lower()
                
                # Check for music-related terms in infobox
                music_terms = [
                    'jazz', 'musician', 'singer', 'vocalist', 'pianist', 'composer',
                    'saxophonist', 'trumpeter', 'bassist', 'drummer', 'guitarist',
                    'occupation', 'instruments', 'genres', 'labels', 'years active',
                    'blues', 'soul', 'r&b', 'gospel', 'folk'
                ]
                found_infobox_terms = [term for term in music_terms if term in infobox_text]
                if found_infobox_terms:
                    confidence_score += 40  # Strong signal
                    reasons.append(f"Infobox contains music terms: {', '.join(found_infobox_terms[:3])}")
            
            # Check for jazz musician keywords in main content
            jazz_keywords = [
                'jazz', 'musician', 'singer', 'vocalist', 'performer', 'artist',
                'saxophonist', 'pianist', 'trumpeter', 'bassist', 'drummer', 
                'guitarist', 'composer', 'bandleader', 'music', 'song',
                'album', 'recording', 'blues', 'soul', 'r&b', 'rhythm and blues',
                'performance', 'concert', 'stage', 'recorded', 'released'
            ]
            # Search in first 2000 characters instead of 1000
            found_keywords = [kw for kw in jazz_keywords if kw in page_text[:2000]]
            if found_keywords:
                confidence_score += 20  # Reduced since infobox is stronger
                reasons.append(f"Found music keywords: {', '.join(found_keywords[:3])}")
            
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
            # Lower threshold to 30 to be less strict (was 50)
            if confidence_score >= 30:
                return {
                    'valid': True,
                    'confidence': 'high' if confidence_score >= 70 else 'medium' if confidence_score >= 50 else 'low',
                    'reason': '; '.join(reasons) if reasons else 'Page appears valid (score: {})'.format(confidence_score),
                    'score': confidence_score  # Add raw score to return value
                }
            else:
                return {
                    'valid': False,
                    'confidence': 'very_low',
                    'reason': 'Insufficient evidence of correct performer (score: {})'.format(confidence_score),
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
    
    def verify_musicbrainz_reference(self, performer_name, mb_id, context):
        """
        Verify that a MusicBrainz artist ID is valid and refers to the correct performer
        
        Args:
            performer_name: Name of the performer
            mb_id: MusicBrainz artist ID (UUID)
            context: Dict with sample_songs for verification
            
        Returns:
            Dict with 'valid' (bool), 'confidence' (str), 'reason' (str)
        """
        try:
            # MusicBrainz API endpoint
            url = f"https://musicbrainz.org/ws/2/artist/{mb_id}"
            params = {
                'fmt': 'json',
                'inc': 'recordings+tags'
            }
            
            logger.debug(f"Verifying MusicBrainz ID: {mb_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            time.sleep(1.0)  # MusicBrainz rate limiting (1 request per second)
            
            if response.status_code == 404:
                return {
                    'valid': False,
                    'confidence': 'certain',
                    'reason': 'MusicBrainz ID not found (404)'
                }
            elif response.status_code != 200:
                return {
                    'valid': False,
                    'confidence': 'uncertain',
                    'reason': f'API returned status code {response.status_code}'
                }
            
            data = response.json()
            
            # Check name similarity
            mb_name = data.get('name', '').lower()
            performer_name_lower = performer_name.lower()
            
            if mb_name != performer_name_lower:
                # Check if it's a close match (might have different formatting)
                if mb_name not in performer_name_lower and performer_name_lower not in mb_name:
                    return {
                        'valid': False,
                        'confidence': 'high',
                        'reason': f'Name mismatch: DB has "{performer_name}", MusicBrainz has "{data.get("name")}"'
                    }
            
            # Check tags for jazz
            tags = data.get('tags', [])
            jazz_tags = [t for t in tags if 'jazz' in t.get('name', '').lower()]
            
            confidence_score = 50  # Base score for valid ID
            reasons = [f'MusicBrainz name: {data.get("name")}']
            
            if jazz_tags:
                confidence_score += 30
                reasons.append(f'Has jazz tags: {", ".join([t["name"] for t in jazz_tags[:2]])}')
            
            return {
                'valid': True,
                'confidence': 'high' if confidence_score >= 70 else 'medium',
                'reason': '; '.join(reasons)
            }
            
        except requests.RequestException as e:
            logger.error(f"Error verifying MusicBrainz ID {mb_id}: {e}")
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying MusicBrainz: {e}", exc_info=True)
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Verification error: {str(e)}'
            }
    
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
            # Use Wikipedia API to search
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'opensearch',
                'search': performer_name,  # Simplified - just the name
                'limit': 5,  # Check more results
                'namespace': 0,
                'format': 'json'
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            time.sleep(1.0)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            if len(data) < 4 or not data[3]:
                return None
            
            # Get the URLs from the response
            urls = data[3]
            
            # Verify each URL until we find a good match
            for url in urls[:5]:  # Check top 5 results (increased from 3)
                verification = self.verify_wikipedia_reference(performer_name, url, context)
                logger.debug(f"  Checked {url}: valid={verification['valid']}, confidence={verification['confidence']}, score={verification.get('score', 0)}, reason={verification['reason']}")
                # Accept any valid result (low, medium, or high - not very_low)
                if verification['valid']:
                    logger.info(f"  Found Wikipedia: {url} (confidence: {verification['confidence']}, score: {verification.get('score', 0)})")
                    logger.info(f"    Reason: {verification['reason']}")
                    return url
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching Wikipedia for {performer_name}: {e}")
            return None
    
    def search_musicbrainz(self, performer_name, context):
        """
        Search MusicBrainz for a performer
        
        Args:
            performer_name: Name to search for
            context: Dict with sample_songs for verification
            
        Returns:
            MusicBrainz artist ID if found with reasonable confidence, None otherwise
        """
        try:
            url = "https://musicbrainz.org/ws/2/artist/"
            params = {
                'query': f'artist:"{performer_name}" AND tag:jazz',
                'fmt': 'json',
                'limit': 5
            }
            
            response = self.session.get(url, params=params, timeout=10)
            time.sleep(1.0)  # MusicBrainz rate limiting
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            artists = data.get('artists', [])
            
            if not artists:
                return None
            
            # Look for exact or close name match
            for artist in artists:
                artist_name = artist.get('name', '').lower()
                if artist_name == performer_name.lower():
                    mb_id = artist.get('id')
                    # Verify this is the right artist
                    verification = self.verify_musicbrainz_reference(performer_name, mb_id, context)
                    if verification['valid']:
                        logger.info(f"  Found MusicBrainz: {mb_id} (confidence: {verification['confidence']})")
                        logger.info(f"    Reason: {verification['reason']}")
                        return mb_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching MusicBrainz for {performer_name}: {e}")
            return None
    
    def update_performer_references(self, performer_id, new_refs):
        """
        Update external_links for a performer
        
        Args:
            performer_id: UUID of the performer
            new_refs: Dict with keys like 'wikipedia', 'musicbrainz'
        """
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update references: {json.dumps(new_refs)}")
            return True
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Merge new references with existing ones
                    cur.execute("""
                        UPDATE performers
                        SET external_links = COALESCE(external_links, '{}'::jsonb) || %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (json.dumps(new_refs), performer_id))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating performer references: {e}", exc_info=True)
            return False
    
    def process_performer(self, performer):
        """
        Process a single performer - verify existing references and/or find new ones
        
        Args:
            performer: Performer record from database
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"\nProcessing: {performer['name']}")
            logger.info("=" * 60)
            
            # Parse existing external links
            external_links = performer['external_links'] or {}
            wikipedia_url = external_links.get('wikipedia')
            musicbrainz_id = external_links.get('musicbrainz')
            
            # Build context for verification
            context = {
                'birth_date': performer['birth_date'],
                'death_date': performer['death_date'],
                'sample_songs': performer['sample_songs'][:5] if performer['sample_songs'] else []
            }
            
            has_references = bool(wikipedia_url or musicbrainz_id)
            new_refs = {}
            needs_update = False
            
            # Determine which reference types to process
            check_wikipedia = self.reftype_filter is None or self.reftype_filter == 'wikipedia'
            check_musicbrainz = self.reftype_filter is None or self.reftype_filter == 'musicbrainz'
            
            # 1. Verify existing references
            if check_wikipedia and wikipedia_url:
                logger.info(f"  Checking existing Wikipedia: {wikipedia_url}")
                result = self.verify_wikipedia_reference(performer['name'], wikipedia_url, context)
                
                if result['valid']:
                    logger.info(f"  ✓ Wikipedia reference is valid (confidence: {result['confidence']}, score: {result.get('score', 0)})")
                    logger.info(f"    {result['reason']}")
                    self.stats['valid_references'] += 1
                else:
                    logger.warning(f"  ✗ Wikipedia reference may be invalid (confidence: {result['confidence']}, score: {result.get('score', 0)})")
                    logger.warning(f"    {result['reason']}")
                    logger.warning(f"    NOT removing reference - manual review recommended")
                    self.stats['invalid_references'] += 1
            
            if check_musicbrainz and musicbrainz_id:
                logger.info(f"  Checking existing MusicBrainz: {musicbrainz_id}")
                result = self.verify_musicbrainz_reference(performer['name'], musicbrainz_id, context)
                
                if result['valid']:
                    logger.info(f"  ✓ MusicBrainz reference is valid (confidence: {result['confidence']})")
                    logger.info(f"    {result['reason']}")
                    self.stats['valid_references'] += 1
                else:
                    logger.warning(f"  ✗ MusicBrainz reference may be invalid (confidence: {result['confidence']})")
                    logger.warning(f"    {result['reason']}")
                    logger.warning(f"    NOT removing reference - manual review recommended")
                    self.stats['invalid_references'] += 1
            
            # 2. Search for missing references
            if check_wikipedia and not wikipedia_url:
                logger.info("  Searching for Wikipedia reference...")
                found_url = self.search_wikipedia(performer['name'], context)
                if found_url:
                    new_refs['wikipedia'] = found_url
                    needs_update = True
                    self.stats['references_added'] += 1
                else:
                    logger.info("  No Wikipedia reference found")
            
            if check_musicbrainz and not musicbrainz_id:
                logger.info("  Searching for MusicBrainz reference...")
                found_id = self.search_musicbrainz(performer['name'], context)
                if found_id:
                    new_refs['musicbrainz'] = found_id
                    needs_update = True
                    self.stats['references_added'] += 1
                else:
                    logger.info("  No MusicBrainz reference found")
            
            # 3. Update database if we found new references
            if needs_update:
                logger.info(f"  Updating database with new references...")
                success = self.update_performer_references(performer['id'], new_refs)
                if success:
                    logger.info(f"  ✓ Database updated successfully")
                else:
                    logger.error(f"  ✗ Failed to update database")
                    return False
            
            # Track missing references
            if not has_references and not needs_update:
                self.stats['missing_references'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing {performer['name']}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def run(self):
        """Main processing method"""
        logger.info("=" * 80)
        logger.info("PERFORMER REFERENCE VERIFIER")
        logger.info("=" * 80)
        logger.info("")
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Show any active filters
        if self.name_filter:
            logger.info(f"Filter: Processing only performer named '{self.name_filter}'")
        if self.id_filter:
            logger.info(f"Filter: Processing only performer with ID '{self.id_filter}'")
        if self.reftype_filter:
            logger.info(f"Filter: Checking only {self.reftype_filter} references")
        
        if self.name_filter or self.id_filter or self.reftype_filter:
            logger.info("")
        
        # Get all performers
        performers = self.get_performers()
        
        if not performers:
            logger.info("No performers found in database!")
            if self.name_filter:
                logger.info(f"  (No performer found with name '{self.name_filter}')")
            elif self.id_filter:
                logger.info(f"  (No performer found with ID '{self.id_filter}')")
            return True
        
        logger.info(f"Found {len(performers)} performer(s) to process")
        logger.info("")
        
        # Process each performer
        for performer in performers:
            self.stats['performers_processed'] += 1
            self.process_performer(performer)
            
            # Add small delay between performers to be respectful to APIs
            time.sleep(1.5)
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("PROCESSING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Performers processed:     {self.stats['performers_processed']}")
        logger.info(f"Valid references:         {self.stats['valid_references']}")
        logger.info(f"Invalid references:       {self.stats['invalid_references']}")
        logger.info(f"Missing references:       {self.stats['missing_references']}")
        logger.info(f"New references added:     {self.stats['references_added']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("=" * 80)
        
        if self.stats['invalid_references'] > 0:
            logger.info("")
            logger.info("⚠️  Some references appear invalid - manual review recommended")
            logger.info("   Check the log file for details: log/verify_performer_references.log")


def main():
    parser = argparse.ArgumentParser(
        description='Verify and update external references for performers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run verification and updates for all performers
  python verify_performer_references.py
  
  # Process a specific performer by name
  python verify_performer_references.py --name "Miles Davis"
  
  # Process a specific performer by ID
  python verify_performer_references.py --id "561d854a-6a28-4aa7-8c99-323e6ce46c2a"
  
  # Only check Wikipedia references
  python verify_performer_references.py --reftype wikipedia
  
  # Only check MusicBrainz references for a specific performer
  python verify_performer_references.py --name "John Coltrane" --reftype musicbrainz
  
  # Dry run to see what would be done
  python verify_performer_references.py --dry-run
  
  # Enable debug logging
  python verify_performer_references.py --debug
  
  # Combination
  python verify_performer_references.py --name "Miles Davis" --dry-run --debug

This script:
1. Verifies existing Wikipedia and MusicBrainz references
2. Searches for missing references
3. Updates the database with newly found references
4. Logs invalid references for manual review (does not remove them)
        """
    )
    
    # Performer selection arguments
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--name',
        help='Process only the performer with this name'
    )
    group.add_argument(
        '--id',
        help='Process only the performer with this UUID'
    )
    
    parser.add_argument(
        '--reftype',
        choices=['wikipedia', 'musicbrainz'],
        help='Limit to only this reference type (wikipedia or musicbrainz)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create processor and run
    verifier = PerformerReferenceVerifier(
        dry_run=args.dry_run,
        name_filter=args.name,
        id_filter=args.id,
        reftype_filter=args.reftype
    )
    
    try:
        success = verifier.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()