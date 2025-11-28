#!/usr/bin/env python3
"""
Match Authority Recommendations to Recordings

Matches recommendations from song_authority_recommendations table to existing recordings
in the recordings table by comparing artist names, album titles, and years.
Updates recording_id when a confident match is found.

Match Criteria:
- Song ID must match (required)
- Artist name fuzzy match (≥85% similarity)
- Album title fuzzy match (≥85% similarity)
- Recording year exact or ±1 year tolerance

Confidence Levels:
- High: Artist ≥90% + album ≥90% + year match
- Medium: Artist ≥90% + album ≥85%, OR artist ≥80% + album ≥85% + year match
- Low: Artist ≥80% but weak album/year
"""

import sys
import argparse
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from rapidfuzz import fuzz

# Ensure log directory exists BEFORE logging configuration
(Path(__file__).parent / 'logs').mkdir(exist_ok=True)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'logs' / 'match_authority_recommendations.log')
    ]
)
logger = logging.getLogger(__name__)


class AuthorityRecommendationMatcher:
    """Matches authority recommendations to recordings in the database"""
    
    def __init__(self, dry_run: bool = True, min_confidence: str = 'medium',
                 song_name: Optional[str] = None):
        self.dry_run = dry_run
        self.min_confidence = min_confidence
        self.song_name = song_name
        self.stats = {
            'recommendations_processed': 0,
            'high_confidence_matches': 0,
            'medium_confidence_matches': 0,
            'low_confidence_matches': 0,
            'no_matches': 0,
            'multiple_matches': 0,
            'updated': 0,
            'errors': 0
        }
        
        # Matching thresholds
        self.thresholds = {
            'artist_high': 85,
            'artist_medium': 90,
            'artist_low': 80,
            'album_high': 85,
            'album_medium': 90,
            'year_tolerance': 1
        }
    
    def normalize_string(self, s: Optional[str]) -> str:
        """Normalize string for comparison"""
        if not s:
            return ""
        # Remove common variations
        s = s.lower().strip()
        # Remove "the" prefix
        if s.startswith("the "):
            s = s[4:]
        return s
    
    def compare_artists(self, artist1: Optional[str], artist2: Optional[str]) -> float:
        """Compare artist names with fuzzy matching"""
        if not artist1 or not artist2:
            return 0.0
        
        norm1 = self.normalize_string(artist1)
        norm2 = self.normalize_string(artist2)
        
        # Try multiple fuzzy matching approaches
        ratio = fuzz.ratio(norm1, norm2)
        token_sort = fuzz.token_sort_ratio(norm1, norm2)
        
        # Return the best score
        return max(ratio, token_sort)
    
    def compare_albums(self, album1: Optional[str], album2: Optional[str]) -> float:
        """Compare album titles with fuzzy matching"""
        if not album1 or not album2:
            return 0.0
        
        norm1 = self.normalize_string(album1)
        norm2 = self.normalize_string(album2)
        
        # Try multiple fuzzy matching approaches
        ratio = fuzz.ratio(norm1, norm2)
        token_sort = fuzz.token_sort_ratio(norm1, norm2)
        partial = fuzz.partial_ratio(norm1, norm2)
        
        # Return the best score
        return max(ratio, token_sort, partial)
    
    def compare_years(self, year1: Optional[int], year2: Optional[int]) -> bool:
        """Check if years match within tolerance"""
        if not year1 or not year2:
            return False
        
        return abs(year1 - year2) <= self.thresholds['year_tolerance']
    
    def calculate_match_confidence(
        self,
        recommendation: Dict,
        recording: Dict
    ) -> Tuple[str, float, Dict]:
        """
        Calculate match confidence level and detailed scores.
        
        Returns:
            (confidence_level, overall_score, details_dict)
            confidence_level: 'high', 'medium', 'low', or 'none'
        """
        details = {
            'artist_score': 0.0,
            'album_score': 0.0,
            'year_match': False,
            'itunes_match': False  # Keep for future but always False for now
        }
        
        # Note: recordings table doesn't store iTunes IDs separately
        # Future enhancement: could extract from apple_music_url
        
        # Compare artist names
        details['artist_score'] = self.compare_artists(
            recommendation.get('artist_name'),
            recording.get('artist_name')
        )
        
        # Compare album titles
        details['album_score'] = self.compare_albums(
            recommendation.get('album_title'),
            recording.get('album_title')
        )
        
        # Compare years
        details['year_match'] = self.compare_years(
            recommendation.get('recording_year'),
            recording.get('recording_year')
        )
        
        # Determine confidence level
        # Note: iTunes matching not currently available (recordings don't store iTunes IDs)
        if (details['artist_score'] >= self.thresholds['artist_medium'] and
              details['album_score'] >= self.thresholds['album_medium'] and
              details['year_match']):
            confidence = 'high'
            overall_score = 90.0
        elif (details['artist_score'] >= self.thresholds['artist_medium'] and
              details['album_score'] >= self.thresholds['album_high']):
            confidence = 'medium'
            overall_score = 85.0
        elif (details['artist_score'] >= self.thresholds['artist_low'] and
              details['album_score'] >= self.thresholds['album_high'] and
              details['year_match']):
            confidence = 'medium'
            overall_score = 80.0
        elif details['artist_score'] >= self.thresholds['artist_low']:
            confidence = 'low'
            overall_score = details['artist_score']
        else:
            confidence = 'none'
            overall_score = details['artist_score']
        
        return confidence, overall_score, details
    
    def find_matching_recordings(self, recommendation: Dict) -> List[Tuple[Dict, str, float, Dict]]:
        """
        Find all potential recording matches for a recommendation.
        
        Returns:
            List of (recording, confidence_level, overall_score, details)
        """
        song_id = recommendation['song_id']
        artist_name = recommendation.get('artist_name', '')
        
        # If no artist name, can't filter effectively
        if not artist_name:
            logger.debug("No artist name in recommendation, skipping")
            return []
        
        try:
            with get_db_connection() as db:
                with db.cursor() as cur:
                    # First, find performers whose names are similar to the recommendation artist
                    # Use PostgreSQL's similarity function or just get all and filter in Python
                    # For now, get performers with similar names (case-insensitive, contains)
                    normalized_artist = artist_name.lower()
                    
                    # Get recordings with their primary performer (usually the leader)
                    # Filter to only those where at least one performer name is somewhat similar
                    cur.execute("""
                        WITH matching_performers AS (
                            SELECT DISTINCT p.id, p.name
                            FROM performers p
                            WHERE LOWER(p.name) LIKE %s
                               OR LOWER(%s) LIKE '%%' || LOWER(p.name) || '%%'
                               OR LOWER(p.name) LIKE '%%' || LOWER(%s) || '%%'
                        )
                        SELECT 
                            r.id,
                            r.album_title,
                            r.recording_year,
                            r.spotify_url,
                            r.label,
                            STRING_AGG(DISTINCT p.name, ' / ' ORDER BY p.name) as artist_names,
                            -- Get primary performer as main artist
                            (SELECT p2.name 
                             FROM recording_performers rp2
                             JOIN performers p2 ON rp2.performer_id = p2.id
                             WHERE rp2.recording_id = r.id
                             AND (rp2.role = 'leader' OR rp2.role IS NULL)
                             LIMIT 1
                            ) as primary_artist
                        FROM recordings r
                        JOIN recording_performers rp ON r.id = rp.recording_id
                        JOIN matching_performers p ON rp.performer_id = p.id
                        WHERE r.song_id = %s
                        GROUP BY r.id
                        LIMIT 50
                    """, (f'%{normalized_artist}%', artist_name, artist_name, song_id))
                    
                    recordings = cur.fetchall()
                    
                    if recordings:
                        logger.debug(f"Found {len(recordings)} recordings with similar artist names")
                        for rec in recordings:
                            logger.debug(f"  → {rec.get('artist_names', 'No artist')} - {rec.get('album_title', 'No album')} ({rec.get('recording_year', 'No year')})")
                    else:
                        logger.debug(f"No recordings found for artist name similar to: {artist_name}")
                    
                    matches = []
                    for recording in recordings:
                        # Create a dict with artist_name for matching
                        rec_dict = dict(recording)
                        # Use primary artist if available, otherwise all artist names
                        rec_dict['artist_name'] = recording['primary_artist'] or recording['artist_names']
                        
                        confidence, score, details = self.calculate_match_confidence(
                            recommendation,
                            rec_dict
                        )
                        
                        # Log detailed comparison
                        logger.debug(f"\nComparing with recording: {rec_dict['artist_name']} - {rec_dict.get('album_title', 'No album')}")
                        logger.debug(f"  Artist: {details['artist_score']:.1f}% similarity")
                        logger.debug(f"    Recommend: '{recommendation.get('artist_name')}'")
                        logger.debug(f"    Recording: '{rec_dict['artist_name']}'")
                        logger.debug(f"  Album: {details['album_score']:.1f}% similarity")
                        logger.debug(f"    Recommend: '{recommendation.get('album_title')}'")
                        logger.debug(f"    Recording: '{rec_dict.get('album_title')}'")
                        logger.debug(f"  Year: {'MATCH ✓' if details['year_match'] else 'NO MATCH ✗'}")
                        logger.debug(f"    Recommend: {recommendation.get('recording_year')}")
                        logger.debug(f"    Recording: {rec_dict.get('recording_year')}")
                        logger.debug(f"  → RESULT: {confidence.upper()} confidence ({score:.1f}%)")
                        
                        if confidence != 'none':
                            matches.append((rec_dict, confidence, score, details))
                    
                    # Sort by confidence level first (high > medium > low), then by score
                    confidence_order = {'high': 3, 'medium': 2, 'low': 1, 'none': 0}
                    matches.sort(key=lambda x: (confidence_order.get(x[1], 0), x[2]), reverse=True)
                    return matches
                
        except Exception as e:
            logger.error(f"Error finding matches: {e}", exc_info=True)
            return []
    
    def update_recommendation_recording_id(self, recommendation_id: str, recording_id: str) -> bool:
        """Update recording_id in song_authority_recommendations"""
        if self.dry_run:
            return True
        
        try:
            with get_db_connection() as db:
                with db.cursor() as cur:
                    cur.execute("""
                        UPDATE song_authority_recommendations
                        SET recording_id = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (recording_id, recommendation_id))
                    
                    return True
                
        except Exception as e:
            logger.error(f"Error updating recommendation: {e}", exc_info=True)
            return False
    
    def process_recommendation(self, recommendation: Dict) -> bool:
        """Process a single recommendation and try to match it"""
        self.stats['recommendations_processed'] += 1
        
        rec_id = recommendation['id']
        song_title = recommendation['song_title']
        artist_name = recommendation.get('artist_name', 'Unknown')
        album_title = recommendation.get('album_title', '')
        
        logger.info(f"Song: {song_title}")
        logger.info(f"Recommendation: {artist_name}" +
                    (f" - {album_title}" if album_title else ""))
        logger.debug(f"  Details: artist='{artist_name}', album='{album_title}', year={recommendation.get('recording_year')}")
        
        # Find matching recordings
        matches = self.find_matching_recordings(recommendation)
        
        if not matches:
            logger.info("  No matches found with sufficient confidence")
            self.stats['no_matches'] += 1
            return False
        
        if len(matches) > 1:
            self.stats['multiple_matches'] += 1
            # Count by confidence level
            confidence_counts = {}
            for _, conf, _, _ in matches:
                confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
            
            summary = ", ".join([f"{count} {conf}" for conf, count in sorted(confidence_counts.items(), reverse=True)])
            logger.info(f"  Found {len(matches)} potential matches: {summary}")
        
        # Get best match
        best_recording, confidence, score, details = matches[0]
        
        # Track by confidence level
        if confidence == 'high':
            self.stats['high_confidence_matches'] += 1
        elif confidence == 'medium':
            self.stats['medium_confidence_matches'] += 1
        elif confidence == 'low':
            self.stats['low_confidence_matches'] += 1
        
        # Check if confidence meets minimum threshold
        confidence_levels = {'high': 2, 'medium': 1, 'low': 0}
        min_level = confidence_levels.get(self.min_confidence, 1)
        current_level = confidence_levels.get(confidence, 0)
        
        if current_level < min_level:
            logger.info(f"  ⚠ Best match is '{confidence}' confidence but minimum is '{self.min_confidence}'")
            logger.info(f"    Recording: {best_recording.get('artist_name', 'Unknown')} - {best_recording.get('album_title', 'No album')} ({best_recording.get('recording_year', 'No year')})")
            logger.debug(f"    Scores: Artist {details['artist_score']:.1f}%, Album {details['album_score']:.1f}%, Year {'✓' if details['year_match'] else '✗'}")
            return False
        
        # Log match details
        mode = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"  ✓ {mode}MATCHED ({confidence.upper()}, {score:.1f}%)")
        logger.info(f"    Recording: {best_recording.get('artist_name', 'Unknown')} - {best_recording.get('album_title', 'No album')} ({best_recording.get('recording_year', 'No year')})")
        logger.debug(f"    Scores: Artist {details['artist_score']:.1f}%, Album {details['album_score']:.1f}%, Year {'✓' if details['year_match'] else '✗'}")
        
        # Update recording_id
        if self.update_recommendation_recording_id(rec_id, best_recording['id']):
            self.stats['updated'] += 1
            return True
        else:
            self.stats['errors'] += 1
            return False
    
    def get_unmatched_recommendations(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch recommendations that don't have recording_id set"""
        if self.song_name:
            logger.info(f"Fetching unmatched recommendations for song: '{self.song_name}'...")
        else:
            logger.info("Fetching unmatched recommendations...")
        
        try:
            with get_db_connection() as db:
                with db.cursor() as cur:
                    query = """
                        SELECT 
                            sar.id,
                            sar.song_id,
                            sar.artist_name,
                            sar.album_title,
                            sar.recording_year,
                            sar.itunes_album_id,
                            sar.itunes_track_id,
                            sar.source,
                            s.title as song_title
                        FROM song_authority_recommendations sar
                        JOIN songs s ON sar.song_id = s.id
                        WHERE sar.recording_id IS NULL
                    """
                    params = []
                    
                    # Filter by song name if provided
                    if self.song_name:
                        query += " AND LOWER(s.title) = LOWER(%s)"
                        params.append(self.song_name)
                    
                    query += " ORDER BY s.title, sar.artist_name"
                    
                    if limit:
                        query += f" LIMIT {limit}"
                    
                    cur.execute(query, params)
                    recommendations = cur.fetchall()
                    
                    if self.song_name and not recommendations:
                        # Check if song exists at all
                        cur.execute("""
                            SELECT s.title, COUNT(sar.id) as total_recs
                            FROM songs s
                            LEFT JOIN song_authority_recommendations sar ON s.id = sar.song_id
                            WHERE LOWER(s.title) = LOWER(%s)
                            GROUP BY s.id
                        """, (self.song_name,))
                        song_info = cur.fetchone()
                        
                        if song_info:
                            logger.info(f"✓ Song '{song_info['title']}' exists with {song_info['total_recs']} total recommendations (all may be matched)")
                        else:
                            logger.warning(f"⚠ No song found with title: '{self.song_name}'")
                    
                    logger.info(f"✓ Found {len(recommendations)} unmatched recommendations")
                    return recommendations
                
        except Exception as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return []
    
    def run(self, limit: Optional[int] = None) -> bool:
        """Main execution method"""
        logger.info("="*80)
        logger.info("MATCH AUTHORITY RECOMMENDATIONS TO RECORDINGS")
        logger.info("="*80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Minimum confidence: {self.min_confidence}")
        if self.song_name:
            logger.info(f"Song filter: '{self.song_name}'")
        logger.info("")
        
        # Get unmatched recommendations
        recommendations = self.get_unmatched_recommendations(limit)
        if not recommendations:
            logger.info("No unmatched recommendations found")
            return True
        
        # Process each recommendation
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"\n[{i}/{len(recommendations)}] ============================================")
            try:
                self.process_recommendation(rec)
            except Exception as e:
                logger.error(f"Error processing recommendation: {e}", exc_info=True)
                self.stats['errors'] += 1
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print statistics summary"""
        logger.info("\n" + "="*80)
        logger.info("MATCHING SUMMARY")
        logger.info("="*80)
        logger.info(f"Recommendations processed:   {self.stats['recommendations_processed']}")
        logger.info(f"High confidence matches:     {self.stats['high_confidence_matches']}")
        logger.info(f"Medium confidence matches:   {self.stats['medium_confidence_matches']}")
        logger.info(f"Low confidence matches:      {self.stats['low_confidence_matches']}")
        logger.info(f"No matches found:            {self.stats['no_matches']}")
        logger.info(f"Multiple matches found:      {self.stats['multiple_matches']}")
        logger.info(f"Recommendations updated:     {self.stats['updated']}")
        logger.info(f"Errors:                      {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Match authority recommendations to existing recordings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview matches without updating (default)
  python match_authority_recommendations.py --dry-run
  
  # Match and update with high confidence threshold
  python match_authority_recommendations.py --live --min-confidence high
  
  # Match with medium confidence (more matches)
  python match_authority_recommendations.py --live --min-confidence medium
  
  # Process only first 10 recommendations
  python match_authority_recommendations.py --limit 10
  
  # Process recommendations for a specific song only
  python match_authority_recommendations.py --name "Body and Soul" --debug
  
  # With debug logging
  python match_authority_recommendations.py --debug

Confidence Levels:
  high   - Artist ≥90% + album ≥90% + year match
  medium - Artist ≥90% + album ≥85%, OR artist ≥80% + album ≥85% + year match
  low    - Artist ≥80% but weak album/year match
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Preview matches without updating database (default)'
    )
    
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually update the database (overrides --dry-run)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--min-confidence',
        choices=['high', 'medium', 'low'],
        default='medium',
        help='Minimum confidence level for matching (default: medium)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of recommendations to process'
    )
    
    parser.add_argument(
        '--name',
        type=str,
        metavar='SONG_NAME',
        help='Limit to recommendations for a specific song title (case-insensitive)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine dry_run mode
    dry_run = not args.live
    
    # Create matcher and run
    matcher = AuthorityRecommendationMatcher(
        dry_run=dry_run,
        min_confidence=args.min_confidence,
        song_name=args.name
    )
    
    try:
        success = matcher.run(limit=args.limit)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()