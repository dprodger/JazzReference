#!/usr/bin/env python3
"""
Repair Performers Missing MusicBrainz IDs

This script finds performers in the database that lack MusicBrainz IDs and attempts
to find and assign the correct MBID by searching MusicBrainz.

The script handles several categories of performers:
1. Famous jazz artists who should have MBIDs (Ella Fitzgerald, Dizzy Gillespie, etc.)
2. Band/ensemble names that may or may not have MBIDs
3. Performers with ambiguous names that need manual review
4. Invalid entries (e.g., "American jazz" which is a museum, not a performer)

Usage:
  # Analyze performers without MBIDs (dry-run)
  python repair_performers_missing_mbid.py --dry-run

  # Repair performers, updating MBIDs where confident matches are found
  python repair_performers_missing_mbid.py

  # Repair a specific performer by name
  python repair_performers_missing_mbid.py --name "Ella Fitzgerald"

  # Limit to first N performers
  python repair_performers_missing_mbid.py --limit 10

  # Show detailed matching info
  python repair_performers_missing_mbid.py --verbose
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Configure logging
LOG_DIR = Path(__file__).parent / 'log'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'repair_performers_missing_mbid.log')
    ]
)
logger = logging.getLogger(__name__)

# Known invalid performers that should be flagged for removal
INVALID_PERFORMERS = {
    'american jazz',  # This is the American Jazz Museum, not a performer
}

# Known band suffixes that indicate this might be a group, not individual
GROUP_SUFFIXES = [
    ' trio', ' quartet', ' quintet', ' sextet', ' septet', ' octet',
    ' orchestra', ' band', ' ensemble', ' all stars', ' all-stars',
]


class PerformerMBIDRepairer:
    """Repairs performers missing MusicBrainz IDs"""

    def __init__(self, dry_run: bool = False, force_refresh: bool = False,
                 verbose: bool = False, min_score: int = 95):
        """
        Initialize the repairer.

        Args:
            dry_run: If True, don't make changes, just report
            force_refresh: If True, bypass MusicBrainz cache
            verbose: If True, show detailed matching info
            min_score: Minimum MusicBrainz search score to consider a match (0-100)
        """
        self.dry_run = dry_run
        self.force_refresh = force_refresh
        self.verbose = verbose
        self.min_score = min_score
        self.mb_searcher = MusicBrainzSearcher(force_refresh=force_refresh)
        self.stats = {
            'performers_found': 0,
            'performers_updated': 0,
            'performers_skipped_low_score': 0,
            'performers_skipped_ambiguous': 0,
            'performers_flagged_invalid': 0,
            'performers_flagged_wrong_bio': 0,
            'performers_no_match': 0,
            'errors': 0
        }
        # Track performers that need manual review
        self.manual_review = []

    def find_performers_without_mbid(self, name_filter: Optional[str] = None,
                                      limit: Optional[int] = None) -> List[Dict]:
        """
        Find performers in the database without MusicBrainz IDs.

        Args:
            name_filter: Optional filter by performer name
            limit: Optional limit on number of performers

        Returns:
            List of performer dicts
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        p.id,
                        p.name,
                        p.biography,
                        p.birth_date,
                        p.death_date,
                        p.wikipedia_url,
                        p.sort_name,
                        p.artist_type,
                        p.created_at,
                        (SELECT COUNT(*) FROM recording_performers rp WHERE rp.performer_id = p.id) as recording_count
                    FROM performers p
                    WHERE p.musicbrainz_id IS NULL
                """
                params = []

                if name_filter:
                    query += " AND LOWER(p.name) LIKE LOWER(%s)"
                    params.append(f'%{name_filter}%')

                query += " ORDER BY p.name"

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query, params if params else None)
                return [dict(row) for row in cur.fetchall()]

    def is_group_name(self, name: str) -> bool:
        """Check if a name appears to be a group/band name"""
        name_lower = name.lower()
        for suffix in GROUP_SUFFIXES:
            if suffix in name_lower:
                return True
        # Check for "X and His/Her Y" pattern
        if ' and his ' in name_lower or ' and her ' in name_lower:
            return True
        return False

    def is_invalid_performer(self, name: str) -> bool:
        """Check if this is a known invalid performer entry"""
        return name.lower().strip() in INVALID_PERFORMERS

    def search_musicbrainz_for_performer(self, performer: Dict) -> Optional[Dict]:
        """
        Search MusicBrainz for a matching artist.

        Args:
            performer: Performer dict from database

        Returns:
            Best matching MusicBrainz artist dict, or None
        """
        name = performer['name']

        # Search MusicBrainz
        results = self.mb_searcher.search_musicbrainz_artist(name)

        if not results:
            return None

        # Find best match
        best_match = None
        best_score = 0

        for artist in results:
            score = artist.get('score', 0)
            mb_name = artist.get('name', '').lower()
            search_name = name.lower()

            # Exact name match gets priority
            if mb_name == search_name and score >= self.min_score:
                if score > best_score:
                    best_match = artist
                    best_score = score

            # For groups, also accept matches where MB name contains our name
            elif self.is_group_name(name):
                if search_name in mb_name or mb_name in search_name:
                    if score >= self.min_score and score > best_score:
                        best_match = artist
                        best_score = score

        return best_match

    def validate_match(self, performer: Dict, mb_artist: Dict) -> Tuple[bool, str]:
        """
        Validate that a MusicBrainz match is correct.

        Args:
            performer: Our database performer
            mb_artist: MusicBrainz artist result

        Returns:
            Tuple of (is_valid, reason)
        """
        mb_name = mb_artist.get('name', '')
        mb_type = mb_artist.get('type', '')
        mb_disambiguation = mb_artist.get('disambiguation', '')
        score = mb_artist.get('score', 0)

        # Check score threshold
        if score < self.min_score:
            return False, f"Score too low: {score} < {self.min_score}"

        # Check name match
        if mb_name.lower() != performer['name'].lower():
            # Allow close matches for groups
            if not self.is_group_name(performer['name']):
                return False, f"Name mismatch: '{mb_name}' vs '{performer['name']}'"

        # For jazz musicians, check if disambiguation suggests non-jazz
        # Be careful not to reject musicians who were also actors (like Frank Sinatra)
        if mb_disambiguation:
            mb_disambig_lower = mb_disambiguation.lower()
            # Only reject if disambiguation clearly indicates non-music profession
            # AND doesn't contain music-related terms
            non_music_indicators = ['swimmer', 'footballer', 'politician',
                                    'baseball player', 'basketball player',
                                    'hockey player', 'wrestler', 'athlete']
            music_indicators = ['singer', 'vocalist', 'musician', 'jazz', 'pianist',
                               'trumpeter', 'saxophonist', 'drummer', 'bassist',
                               'guitarist', 'composer', 'bandleader', 'pop', 'rock']

            has_non_music = any(ind in mb_disambig_lower for ind in non_music_indicators)
            has_music = any(ind in mb_disambig_lower for ind in music_indicators)

            if has_non_music and not has_music:
                return False, f"Non-music disambiguation: '{mb_disambiguation}'"

        # Check if we have birth/death dates that should match
        if performer.get('birth_date') and mb_artist.get('life-span', {}).get('begin'):
            our_birth = str(performer['birth_date'])[:4]  # Get year
            mb_birth = mb_artist['life-span']['begin'][:4]
            if our_birth != mb_birth:
                return False, f"Birth year mismatch: {our_birth} vs {mb_birth}"

        return True, f"Match validated (score: {score})"

    def check_biography_mismatch(self, performer: Dict, mb_artist: Dict) -> Optional[str]:
        """
        Check if the performer's biography appears to be for a different person.

        Args:
            performer: Our database performer
            mb_artist: MusicBrainz artist result

        Returns:
            Warning message if biography seems wrong, None otherwise
        """
        bio = performer.get('biography', '') or ''
        if not bio:
            return None

        bio_lower = bio.lower()
        name = performer['name'].lower()

        # Check for obvious mismatches - keywords that suggest wrong person
        wrong_person_keywords = [
            'swimmer',
            'footballer',
            'baseball',
            'basketball',
            'hockey',
            'politician',
            'guitarist for madness',  # Chris Foreman (Madness guitarist)
            'english band madness',
            'museum',  # American Jazz Museum
            'discography',  # Often indicates a discography page, not a bio
        ]

        for keyword in wrong_person_keywords:
            if keyword in bio_lower:
                # Make sure it's not actually about a jazz musician who happens to mention this
                # Check if 'jazz' appears in the first 300 chars
                if 'jazz' not in bio_lower[:300]:
                    return f"Biography mentions '{keyword}' - may be wrong person"

        return None

    def repair_performer(self, conn, performer: Dict) -> bool:
        """
        Attempt to repair a single performer by finding and assigning MBID.

        Args:
            conn: Database connection
            performer: Performer dict

        Returns:
            True if repaired, False otherwise
        """
        name = performer['name']
        performer_id = performer['id']
        recording_count = performer.get('recording_count', 0)

        logger.info(f"  Processing: {name} ({recording_count} recordings)")

        # Check for known invalid performers
        if self.is_invalid_performer(name):
            logger.warning(f"    INVALID: This is not a performer (flagged for removal)")
            self.stats['performers_flagged_invalid'] += 1
            self.manual_review.append({
                'performer': performer,
                'reason': 'Invalid entry - not a performer',
                'action': 'DELETE'
            })
            return False

        # Check for biography mismatches before searching
        if performer.get('biography'):
            bio_warning = self.check_biography_mismatch(performer, {})
            if bio_warning:
                logger.warning(f"    WARNING: {bio_warning}")
                self.stats['performers_flagged_wrong_bio'] += 1
                self.manual_review.append({
                    'performer': performer,
                    'reason': bio_warning,
                    'action': 'REVIEW_BIO'
                })

        # Search MusicBrainz
        mb_artist = self.search_musicbrainz_for_performer(performer)

        if not mb_artist:
            logger.info(f"    No MusicBrainz match found")
            self.stats['performers_no_match'] += 1
            return False

        # Validate the match
        is_valid, reason = self.validate_match(performer, mb_artist)

        if self.verbose:
            logger.info(f"    MB Result: {mb_artist.get('name')} (ID: {mb_artist.get('id')})")
            logger.info(f"    Score: {mb_artist.get('score')}, Type: {mb_artist.get('type')}")
            if mb_artist.get('disambiguation'):
                logger.info(f"    Disambiguation: {mb_artist.get('disambiguation')}")
            logger.info(f"    Validation: {reason}")

        if not is_valid:
            logger.info(f"    Skipped: {reason}")
            if 'Score too low' in reason:
                self.stats['performers_skipped_low_score'] += 1
            else:
                self.stats['performers_skipped_ambiguous'] += 1
            return False

        # We have a valid match - update the performer
        mb_id = mb_artist.get('id')
        mb_name = mb_artist.get('name')
        mb_sort_name = mb_artist.get('sort-name')
        mb_type = mb_artist.get('type')
        mb_disambiguation = mb_artist.get('disambiguation')

        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update MBID to: {mb_id}")
            logger.info(f"    [DRY RUN] Would set sort_name to: {mb_sort_name}")
            if mb_type:
                logger.info(f"    [DRY RUN] Would set artist_type to: {mb_type}")
            self.stats['performers_updated'] += 1
            return True

        # Update the database
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE performers
                SET musicbrainz_id = %s,
                    sort_name = COALESCE(sort_name, %s),
                    artist_type = COALESCE(artist_type, %s),
                    disambiguation = COALESCE(disambiguation, %s),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (mb_id, mb_sort_name, mb_type, mb_disambiguation, performer_id))
            conn.commit()

        logger.info(f"    Updated MBID: {mb_id}")
        self.stats['performers_updated'] += 1
        return True

    def run(self, name_filter: Optional[str] = None, limit: Optional[int] = None):
        """
        Run the repair process.

        Args:
            name_filter: Optional filter by performer name
            limit: Optional limit on number of performers
        """
        mode = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{mode}Finding performers without MusicBrainz IDs...")

        performers = self.find_performers_without_mbid(name_filter=name_filter, limit=limit)
        self.stats['performers_found'] = len(performers)

        if not performers:
            logger.info("No performers without MusicBrainz IDs found")
            return

        logger.info(f"Found {len(performers)} performers without MusicBrainz IDs")
        logger.info("")

        with get_db_connection() as conn:
            for i, performer in enumerate(performers, 1):
                logger.info(f"[{i}/{len(performers)}] {performer['name']}")

                try:
                    self.repair_performer(conn, performer)
                except Exception as e:
                    logger.error(f"  Error processing performer: {e}")
                    self.stats['errors'] += 1

                logger.info("")  # Blank line between performers

        self._print_stats()
        self._print_manual_review()

    def _print_stats(self):
        """Print summary statistics"""
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Performers found without MBID:    {self.stats['performers_found']}")
        logger.info(f"Performers updated:               {self.stats['performers_updated']}")
        logger.info(f"Skipped (low score):              {self.stats['performers_skipped_low_score']}")
        logger.info(f"Skipped (ambiguous):              {self.stats['performers_skipped_ambiguous']}")
        logger.info(f"No match found:                   {self.stats['performers_no_match']}")
        logger.info(f"Flagged invalid:                  {self.stats['performers_flagged_invalid']}")
        logger.info(f"Flagged wrong biography:          {self.stats['performers_flagged_wrong_bio']}")
        logger.info(f"Errors:                           {self.stats['errors']}")
        logger.info("=" * 70)

    def _print_manual_review(self):
        """Print items requiring manual review"""
        if not self.manual_review:
            return

        logger.info("")
        logger.info("=" * 70)
        logger.info("ITEMS REQUIRING MANUAL REVIEW")
        logger.info("=" * 70)

        for item in self.manual_review:
            performer = item['performer']
            logger.info(f"\nPerformer: {performer['name']}")
            logger.info(f"  ID: {performer['id']}")
            logger.info(f"  Recordings: {performer.get('recording_count', 0)}")
            logger.info(f"  Reason: {item['reason']}")
            logger.info(f"  Suggested Action: {item['action']}")
            if performer.get('biography'):
                bio_preview = performer['biography'][:200] + '...' if len(performer['biography']) > 200 else performer['biography']
                logger.info(f"  Bio Preview: {bio_preview}")

        logger.info("")
        logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Repair performers missing MusicBrainz IDs'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--name', type=str,
                        help='Filter by performer name')
    parser.add_argument('--limit', type=int,
                        help='Limit number of performers to process')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Bypass MusicBrainz cache')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed matching info')
    parser.add_argument('--min-score', type=int, default=95,
                        help='Minimum MusicBrainz score for auto-matching (default: 95)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    repairer = PerformerMBIDRepairer(
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        verbose=args.verbose,
        min_score=args.min_score
    )

    repairer.run(name_filter=args.name, limit=args.limit)


if __name__ == '__main__':
    main()
