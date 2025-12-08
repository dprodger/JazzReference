#!/usr/bin/env python3
"""
MusicBrainz Orphan Recording Finder

Identifies MusicBrainz recordings that:
1. Have titles matching our target songs
2. Do NOT have a "recording of" relationship to the correct MusicBrainz work

These are candidates for:
- Manual MusicBrainz editing (adding the work relationship)
- Direct import into our database (bypassing work relationship requirement)

Usage:
    python mb_orphan_recordings.py                    # Check all songs with MB work IDs
    python mb_orphan_recordings.py --name "Corcovado" # Check specific song
    python mb_orphan_recordings.py --limit 10         # Check first 10 songs
    python mb_orphan_recordings.py --debug            # Verbose output
"""

import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Ensure log directory exists
(Path(__file__).parent / 'log').mkdir(exist_ok=True)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'log' / 'mb_orphan_recordings.log')
    ]
)
logger = logging.getLogger(__name__)


class OrphanRecordingFinder:
    """Finds MusicBrainz recordings that match song titles but lack work relationships"""

    def __init__(self, cache_days=30, force_refresh=False):
        self.mb = MusicBrainzSearcher(cache_days=cache_days, force_refresh=force_refresh)
        self.stats = {
            'songs_checked': 0,
            'recordings_found': 0,
            'orphans_found': 0,
            'already_linked': 0,
            'wrong_work': 0,
            'api_calls': 0,
            'errors': 0
        }
        # Store orphan details for reporting
        self.orphans = []

    def get_target_songs(self, name_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Get songs that have MusicBrainz work IDs (our target songs)

        Args:
            name_filter: Optional song title filter
            limit: Maximum number of songs to return
        """
        with get_db_connection() as db:
            with db.cursor() as cur:
                query = """
                    SELECT id, title, musicbrainz_id, composer
                    FROM songs
                    WHERE musicbrainz_id IS NOT NULL
                """
                params = []

                if name_filter:
                    query += " AND LOWER(title) LIKE %s"
                    params.append(f'%{name_filter.lower()}%')

                query += " ORDER BY title"

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

    def search_recordings_by_title(self, title: str) -> List[Dict]:
        """
        Search MusicBrainz for recordings with matching title

        Args:
            title: Song title to search for

        Returns:
            List of recording dicts with id, title, artist-credit, etc.
        """
        self.mb.rate_limit()
        self.stats['api_calls'] += 1

        try:
            # Escape special characters for Lucene query
            escaped_title = self.mb._escape_lucene_query(title)

            url = "https://musicbrainz.org/ws/2/recording/"
            params = {
                'query': f'recording:"{escaped_title}"',
                'fmt': 'json',
                'limit': 100  # Get more results to find orphans
            }

            logger.debug(f"  Searching MB recordings: {title}")

            response = self.mb.session.get(url, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"  MB search failed (status {response.status_code})")
                return []

            data = response.json()
            recordings = data.get('recordings', [])

            # Filter to exact title matches (case-insensitive)
            normalized_title = self.mb.normalize_title(title)
            exact_matches = []

            for rec in recordings:
                rec_title = rec.get('title', '')
                if self.mb.normalize_title(rec_title) == normalized_title:
                    exact_matches.append(rec)

            return exact_matches

        except Exception as e:
            logger.error(f"  Error searching recordings: {e}")
            self.stats['errors'] += 1
            return []

    def get_recording_work_links(self, recording_id: str) -> List[Dict]:
        """
        Get work relationships for a recording

        Args:
            recording_id: MusicBrainz recording ID

        Returns:
            List of work relationship dicts
        """
        self.mb.rate_limit()
        self.stats['api_calls'] += 1

        try:
            url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
            params = {
                'inc': 'work-rels',
                'fmt': 'json'
            }

            response = self.mb.session.get(url, params=params, timeout=15)

            if response.status_code != 200:
                return []

            data = response.json()

            # Extract work relationships
            work_links = []
            for relation in data.get('relations', []):
                if relation.get('type') == 'performance':
                    work = relation.get('work', {})
                    work_links.append({
                        'work_id': work.get('id'),
                        'work_title': work.get('title'),
                        'attributes': relation.get('attributes', [])
                    })

            return work_links

        except Exception as e:
            logger.debug(f"  Error getting work links: {e}")
            return []

    def check_song(self, song: Dict) -> List[Dict]:
        """
        Check a single song for orphan recordings

        Args:
            song: Dict with id, title, musicbrainz_id

        Returns:
            List of orphan recording dicts
        """
        song_title = song['title']
        work_id = song['musicbrainz_id']

        logger.info(f"\nChecking: {song_title}")
        logger.debug(f"  Work ID: {work_id}")

        # Search for recordings with matching title
        recordings = self.search_recordings_by_title(song_title)

        if not recordings:
            logger.info(f"  No recordings found with exact title match")
            return []

        logger.info(f"  Found {len(recordings)} recordings with matching title")
        self.stats['recordings_found'] += len(recordings)

        orphans = []

        for rec in recordings:
            rec_id = rec['id']
            rec_title = rec.get('title', '')

            # Get artist credit
            artist_credit = rec.get('artist-credit', [])
            artist_names = ' / '.join([ac.get('name', '') for ac in artist_credit])

            # Get first release date if available
            first_release = rec.get('first-release-date', 'Unknown')

            # Check work relationships
            work_links = self.get_recording_work_links(rec_id)

            if not work_links:
                # No work relationship at all - this is an orphan!
                logger.info(f"    ORPHAN: {artist_names} - {rec_title} ({first_release})")
                logger.debug(f"      Recording ID: {rec_id}")
                logger.debug(f"      https://musicbrainz.org/recording/{rec_id}")

                orphan = {
                    'song_id': song['id'],
                    'song_title': song_title,
                    'expected_work_id': work_id,
                    'recording_id': rec_id,
                    'recording_title': rec_title,
                    'artist': artist_names,
                    'first_release': first_release,
                    'issue': 'no_work_link',
                    'mb_url': f"https://musicbrainz.org/recording/{rec_id}"
                }
                orphans.append(orphan)
                self.stats['orphans_found'] += 1

            else:
                # Has work links - check if any point to our work
                linked_to_correct = False
                linked_work_ids = []

                for link in work_links:
                    linked_work_ids.append(link['work_id'])
                    if link['work_id'] == work_id:
                        linked_to_correct = True
                        break

                if linked_to_correct:
                    logger.debug(f"    OK: {artist_names} (linked to correct work)")
                    self.stats['already_linked'] += 1
                else:
                    # Linked to wrong work
                    logger.info(f"    WRONG WORK: {artist_names} - {rec_title}")
                    logger.debug(f"      Recording ID: {rec_id}")
                    logger.debug(f"      Expected work: {work_id}")
                    logger.debug(f"      Linked to: {', '.join(linked_work_ids)}")

                    orphan = {
                        'song_id': song['id'],
                        'song_title': song_title,
                        'expected_work_id': work_id,
                        'recording_id': rec_id,
                        'recording_title': rec_title,
                        'artist': artist_names,
                        'first_release': first_release,
                        'issue': 'wrong_work',
                        'linked_works': linked_work_ids,
                        'mb_url': f"https://musicbrainz.org/recording/{rec_id}"
                    }
                    orphans.append(orphan)
                    self.stats['wrong_work'] += 1

        return orphans

    def run(self, name_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Run the orphan finder

        Args:
            name_filter: Optional song title filter
            limit: Maximum number of songs to check

        Returns:
            List of all orphan recordings found
        """
        logger.info("=" * 80)
        logger.info("MUSICBRAINZ ORPHAN RECORDING FINDER")
        logger.info("=" * 80)

        if name_filter:
            logger.info(f"Song filter: '{name_filter}'")
        if limit:
            logger.info(f"Limit: {limit} songs")

        # Get target songs
        songs = self.get_target_songs(name_filter=name_filter, limit=limit)

        if not songs:
            logger.info("No songs found with MusicBrainz work IDs")
            return []

        logger.info(f"Found {len(songs)} songs to check")

        all_orphans = []

        for i, song in enumerate(songs, 1):
            logger.info(f"\n[{i}/{len(songs)}] {'=' * 40}")
            self.stats['songs_checked'] += 1

            orphans = self.check_song(song)
            all_orphans.extend(orphans)

            # Be nice to MusicBrainz
            if i < len(songs):
                time.sleep(0.5)

        self.orphans = all_orphans
        self._print_summary()

        return all_orphans

    def _print_summary(self):
        """Print summary statistics"""
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Songs checked:           {self.stats['songs_checked']}")
        logger.info(f"Recordings found:        {self.stats['recordings_found']}")
        logger.info(f"Already linked:          {self.stats['already_linked']}")
        logger.info(f"Orphans (no work link):  {self.stats['orphans_found']}")
        logger.info(f"Wrong work link:         {self.stats['wrong_work']}")
        logger.info(f"API calls made:          {self.stats['api_calls']}")
        logger.info(f"Errors:                  {self.stats['errors']}")

        if self.orphans:
            logger.info("\n" + "-" * 80)
            logger.info("ORPHAN RECORDINGS (need MusicBrainz editing or direct import)")
            logger.info("-" * 80)

            # Group by song
            by_song = {}
            for orphan in self.orphans:
                song_title = orphan['song_title']
                if song_title not in by_song:
                    by_song[song_title] = []
                by_song[song_title].append(orphan)

            for song_title, orphans in sorted(by_song.items()):
                logger.info(f"\n{song_title}:")
                for orphan in orphans:
                    issue = "NO WORK LINK" if orphan['issue'] == 'no_work_link' else "WRONG WORK"
                    logger.info(f"  [{issue}] {orphan['artist']} ({orphan['first_release']})")
                    logger.info(f"    {orphan['mb_url']}")

        logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Find MusicBrainz recordings that match song titles but lack work relationships'
    )
    parser.add_argument('--name', help='Filter by song name (partial match)')
    parser.add_argument('--limit', type=int, help='Maximum number of songs to check')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--force-refresh', action='store_true', help='Bypass cache')
    parser.add_argument('--cache-days', type=int, default=30, help='Cache expiration in days')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    finder = OrphanRecordingFinder(
        cache_days=args.cache_days,
        force_refresh=args.force_refresh
    )

    orphans = finder.run(
        name_filter=args.name,
        limit=args.limit
    )

    # Exit with non-zero if orphans found (useful for CI/scripts)
    sys.exit(0 if not orphans else 1)


if __name__ == '__main__':
    main()
