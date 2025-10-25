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
from wiki_utils import WikipediaSearcher
from db_utils import get_db_connection

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
    
    def __init__(self, dry_run=False, name_filter=None, id_filter=None, reftype_filter=None, only_new=False, force_refresh=False):
        """
        Initialize verifier
        
        Args:
            dry_run: If True, show what would be done without making changes
            name_filter: If provided, only process performer with this name
            id_filter: If provided, only process performer with this UUID
            reftype_filter: If provided, only check this reference type ('wikipedia' or 'musicbrainz')
            only_new: If True, only process performers missing the specified reference type(s)
            force_refresh: If True, bypass Wikipedia cache and fetch fresh data
        """
        self.dry_run = dry_run
        self.name_filter = name_filter
        self.id_filter = id_filter
        self.reftype_filter = reftype_filter
        self.only_new = only_new
        self.force_refresh = force_refresh
        
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
            'references_removed': 0,  # ADDED: Track removed references
            'errors': 0
        }
        
        self.wiki_searcher = WikipediaSearcher(
            cache_dir='cache/wikipedia',
            cache_days=7,
            force_refresh=force_refresh
        )
    
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
                    'reason': 'MusicBrainz ID not found (404)',
                    'score': 0
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
                        'reason': f'Name mismatch: DB has "{performer_name}", MusicBrainz has "{data.get("name")}"',
                        'score': 0
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
                'reason': '; '.join(reasons),
                'score': confidence_score
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
                verification = self.wiki_searcher.verify_wikipedia_reference(performer_name, url, context)
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

        if self.force_refresh:
            logger.info(f"    FORCE REFRESH MODE - Bypassing Wikipedia cache ***")
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
    
    # ADDED: New method to remove a reference
    def remove_performer_reference(self, performer_id, ref_type):
        """
        Remove a specific reference from external_links
        
        Args:
            performer_id: UUID of the performer
            ref_type: Reference type to remove ('wikipedia' or 'musicbrainz')
        """
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would remove {ref_type} reference")
            return True
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Remove the specified key from the JSONB object
                    cur.execute("""
                        UPDATE performers
                        SET external_links = external_links - %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (ref_type, performer_id))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error removing performer reference: {e}", exc_info=True)
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
            
            # Check if we should skip this performer based on --onlynew flag
            if self.only_new:
                # Determine which refs we're checking
                check_wikipedia = self.reftype_filter is None or self.reftype_filter == 'wikipedia'
                check_musicbrainz = self.reftype_filter is None or self.reftype_filter == 'musicbrainz'
                
                # Skip if all the refs we're checking already exist
                skip = True
                if check_wikipedia and not wikipedia_url:
                    skip = False  # Wikipedia is missing, so don't skip
                if check_musicbrainz and not musicbrainz_id:
                    skip = False  # MusicBrainz is missing, so don't skip
                
                if skip:
                    logger.info(f"  Skipping (already has all requested references)")
                    return True
            
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
            
            # If --onlynew is set, only search for missing refs, don't verify existing ones
            if self.only_new:
                # Skip verification of existing refs
                if check_wikipedia and wikipedia_url:
                    check_wikipedia = False  # Don't check it
                if check_musicbrainz and musicbrainz_id:
                    check_musicbrainz = False  # Don't check it
            
            # 1. Verify existing references (unless --onlynew is set)
            if not self.only_new:
                if check_wikipedia and wikipedia_url:
                    logger.info(f"  Checking existing Wikipedia: {wikipedia_url}")
                    result = self.wiki_searcher.verify_wikipedia_reference(performer['name'], wikipedia_url, context)
                    
                    if result['valid']:
                        logger.info(f"  ✓ Wikipedia reference is valid (confidence: {result['confidence']}, score: {result.get('score', 0)})")
                        logger.info(f"    {result['reason']}")
                        self.stats['valid_references'] += 1
                    else:
                        # MODIFIED: Check if score is 0 or confidence is very_low - if so, remove it
                        score = result.get('score', 0)
                        confidence = result['confidence']
                        
                        if score == 0 or confidence == 'very_low':
                            logger.warning(f"  ✗ Wikipedia reference is invalid (confidence: {confidence}, score: {score})")
                            logger.warning(f"    {result['reason']}")
                            logger.warning(f"  🗑️  REMOVING invalid Wikipedia reference")
                            
                            success = self.remove_performer_reference(performer['id'], 'wikipedia')
                            if success:
                                logger.info(f"  ✓ Wikipedia reference removed successfully")
                                self.stats['references_removed'] += 1
                            else:
                                logger.error(f"  ✗ Failed to remove Wikipedia reference")
                                self.stats['errors'] += 1
                            
                            self.stats['invalid_references'] += 1
                        else:
                            logger.warning(f"  ✗ Wikipedia reference may be invalid (confidence: {confidence}, score: {score})")
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
                        # MODIFIED: Check if score is 0 or confidence is very_low/certain - if so, remove it
                        score = result.get('score', 0)
                        confidence = result['confidence']
                        
                        if score == 0 or confidence in ['very_low', 'certain']:
                            logger.warning(f"  ✗ MusicBrainz reference is invalid (confidence: {confidence}, score: {score})")
                            logger.warning(f"    {result['reason']}")
                            logger.warning(f"  🗑️  REMOVING invalid MusicBrainz reference")
                            
                            success = self.remove_performer_reference(performer['id'], 'musicbrainz')
                            if success:
                                logger.info(f"  ✓ MusicBrainz reference removed successfully")
                                self.stats['references_removed'] += 1
                            else:
                                logger.error(f"  ✗ Failed to remove MusicBrainz reference")
                                self.stats['errors'] += 1
                            
                            self.stats['invalid_references'] += 1
                        else:
                            logger.warning(f"  ✗ MusicBrainz reference may be invalid (confidence: {confidence}, score: {score})")
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
        if self.only_new:
            logger.info(f"Filter: Only processing performers missing the specified reference(s)")
        
        if self.name_filter or self.id_filter or self.reftype_filter or self.only_new:
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
        logger.info(f"References removed:       {self.stats['references_removed']}")  # ADDED
        logger.info(f"Missing references:       {self.stats['missing_references']}")
        logger.info(f"New references added:     {self.stats['references_added']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("=" * 80)
        
        # MODIFIED: Update warning message
        if self.stats['invalid_references'] > self.stats['references_removed']:
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

  # Force refresh Wikipedia pages (bypass cache)
  python verify_performer_references.py --force-refresh
    
  # Combination
  python verify_performer_references.py --name "Miles Davis" --dry-run --debug

This script:
1. Verifies existing Wikipedia and MusicBrainz references
2. Searches for missing references
3. Updates the database with newly found references
4. Removes references with score 0 or very_low confidence (unless --dry-run)
5. Caches Wikipedia pages for 7 days (use --force-refresh to bypass cache)
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
        '--onlynew',
        action='store_true',
        help='Only process performers missing the specified reference type(s)'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Bypass Wikipedia cache and fetch fresh data from Wikipedia'
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
        reftype_filter=args.reftype,
        only_new=args.onlynew,
        force_refresh=args.force_refresh
        
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