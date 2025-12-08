#!/usr/bin/env python3
"""
Orphan Recording Manager

Discovers MusicBrainz orphan recordings and enriches them with Spotify matches.
Populates the orphan_recordings table for admin review.

Usage:
    python orphan_manager.py discover --name "By The River Sainte Marie"
    python orphan_manager.py enrich --name "By The River Sainte Marie"
    python orphan_manager.py both --name "By The River Sainte Marie"
"""

import sys
import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from scripts directory
load_dotenv(Path(__file__).parent / '.env')

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher
from spotify_matcher import SpotifyMatcher
from spotify_matching import calculate_similarity, normalize_for_comparison

# Ensure log directory exists
(Path(__file__).parent / 'log').mkdir(exist_ok=True)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'log' / 'orphan_manager.log')
    ]
)
logger = logging.getLogger(__name__)


class OrphanManager:
    """Manages discovery and enrichment of orphan recordings"""

    def __init__(self, cache_days=30, force_refresh=False):
        self.mb = MusicBrainzSearcher(cache_days=cache_days, force_refresh=force_refresh)
        self.spotify = None  # Lazy-loaded
        self.force_refresh = force_refresh
        self.stats = {
            'songs_processed': 0,
            'orphans_discovered': 0,
            'orphans_inserted': 0,
            'orphans_updated': 0,
            'spotify_matches': 0,
            'spotify_no_match': 0,
            'errors': 0
        }

    def get_spotify_matcher(self):
        """Lazy-load Spotify matcher"""
        if self.spotify is None:
            self.spotify = SpotifyMatcher(
                dry_run=False,
                strict_mode=False,
                force_refresh=self.force_refresh
            )
        return self.spotify

    def get_songs(self, name_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get songs with MusicBrainz work IDs"""
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

    def search_mb_recordings(self, title: str) -> List[Dict]:
        """Search MusicBrainz for recordings with matching title"""
        self.mb.rate_limit()

        try:
            escaped_title = self.mb._escape_lucene_query(title)
            url = "https://musicbrainz.org/ws/2/recording/"
            params = {
                'query': f'recording:"{escaped_title}"',
                'fmt': 'json',
                'limit': 100
            }

            response = self.mb.session.get(url, params=params, timeout=15)
            if response.status_code != 200:
                return []

            data = response.json()
            recordings = data.get('recordings', [])

            # Filter to exact title matches
            normalized_title = self.mb.normalize_title(title)
            return [r for r in recordings
                    if self.mb.normalize_title(r.get('title', '')) == normalized_title]

        except Exception as e:
            logger.error(f"Error searching MB recordings: {e}")
            return []

    def get_recording_work_links(self, recording_id: str) -> List[Dict]:
        """Get work relationships for a recording"""
        self.mb.rate_limit()

        try:
            url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
            params = {'inc': 'work-rels', 'fmt': 'json'}

            response = self.mb.session.get(url, params=params, timeout=15)
            if response.status_code != 200:
                return []

            data = response.json()

            work_links = []
            for relation in data.get('relations', []):
                if relation.get('type') == 'performance':
                    work = relation.get('work', {})
                    work_links.append({
                        'work_id': work.get('id'),
                        'work_title': work.get('title')
                    })

            return work_links

        except Exception as e:
            logger.debug(f"Error getting work links: {e}")
            return []

    def get_recording_releases(self, recording_id: str) -> List[Dict]:
        """Get all releases that contain this recording"""
        self.mb.rate_limit()

        try:
            url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
            params = {'inc': 'releases', 'fmt': 'json'}

            response = self.mb.session.get(url, params=params, timeout=15)
            if response.status_code != 200:
                return []

            data = response.json()

            releases = []
            for release in data.get('releases', []):
                releases.append({
                    'id': release.get('id'),
                    'title': release.get('title'),
                    'date': release.get('date', ''),
                    'status': release.get('status', ''),
                    'country': release.get('country', '')
                })

            # Sort by date (oldest first)
            releases.sort(key=lambda r: r.get('date', 'zzzz'))
            return releases

        except Exception as e:
            logger.debug(f"Error getting releases: {e}")
            return []

    def discover_orphans(self, song: Dict) -> List[Dict]:
        """Discover orphan recordings for a song"""
        song_title = song['title']
        work_id = song['musicbrainz_id']

        logger.info(f"Discovering orphans for: {song_title}")
        logger.debug(f"  Work ID: {work_id}")

        recordings = self.search_mb_recordings(song_title)
        if not recordings:
            logger.info(f"  No recordings found with matching title")
            return []

        logger.info(f"  Found {len(recordings)} recordings with matching title")

        orphans = []
        for rec in recordings:
            rec_id = rec['id']
            rec_title = rec.get('title', '')

            # Get artist credit
            artist_credit = rec.get('artist-credit', [])
            artist_names = ' / '.join([ac.get('name', '') for ac in artist_credit])
            artist_ids = [ac.get('artist', {}).get('id') for ac in artist_credit if ac.get('artist')]

            # Get first release date and length
            first_release = rec.get('first-release-date', '')
            length_ms = rec.get('length')

            # Check work relationships
            work_links = self.get_recording_work_links(rec_id)

            issue_type = None
            linked_work_ids = []

            if not work_links:
                issue_type = 'no_work_link'
            else:
                linked_to_correct = any(link['work_id'] == work_id for link in work_links)
                if not linked_to_correct:
                    issue_type = 'wrong_work'
                    linked_work_ids = [link['work_id'] for link in work_links]

            if issue_type:
                logger.info(f"    ORPHAN ({issue_type}): {artist_names}")

                # Fetch releases for this recording
                releases = self.get_recording_releases(rec_id)
                logger.debug(f"      Found {len(releases)} releases")

                orphan = {
                    'song_id': song['id'],
                    'mb_recording_id': rec_id,
                    'mb_recording_title': rec_title,
                    'mb_artist_credit': artist_names[:500],
                    'mb_artist_ids': artist_ids,
                    'mb_first_release_date': first_release,
                    'mb_length_ms': length_ms,
                    'mb_disambiguation': rec.get('disambiguation', ''),
                    'issue_type': issue_type,
                    'linked_work_ids': linked_work_ids if linked_work_ids else None,
                    'mb_releases': releases  # Add releases data
                }
                orphans.append(orphan)
                self.stats['orphans_discovered'] += 1
            else:
                logger.debug(f"    OK: {artist_names} (linked to correct work)")

        return orphans

    def save_orphans(self, orphans: List[Dict]) -> int:
        """Save orphans to database (upsert)"""
        import json

        if not orphans:
            return 0

        saved = 0
        with get_db_connection() as db:
            with db.cursor() as cur:
                for orphan in orphans:
                    try:
                        # Serialize releases to JSON for JSONB column
                        releases_json = json.dumps(orphan.get('mb_releases', []))

                        cur.execute("""
                            INSERT INTO orphan_recordings (
                                song_id, mb_recording_id, mb_recording_title,
                                mb_artist_credit, mb_artist_ids, mb_first_release_date,
                                mb_length_ms, mb_disambiguation, issue_type, linked_work_ids,
                                mb_releases, discovered_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                            )
                            ON CONFLICT (song_id, mb_recording_id) DO UPDATE SET
                                mb_recording_title = EXCLUDED.mb_recording_title,
                                mb_artist_credit = EXCLUDED.mb_artist_credit,
                                mb_artist_ids = EXCLUDED.mb_artist_ids,
                                mb_first_release_date = EXCLUDED.mb_first_release_date,
                                mb_length_ms = EXCLUDED.mb_length_ms,
                                mb_disambiguation = EXCLUDED.mb_disambiguation,
                                issue_type = EXCLUDED.issue_type,
                                linked_work_ids = EXCLUDED.linked_work_ids,
                                mb_releases = EXCLUDED.mb_releases,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            orphan['song_id'],
                            orphan['mb_recording_id'],
                            orphan['mb_recording_title'],
                            orphan['mb_artist_credit'],
                            orphan['mb_artist_ids'],
                            orphan['mb_first_release_date'],
                            orphan['mb_length_ms'],
                            orphan['mb_disambiguation'],
                            orphan['issue_type'],
                            orphan['linked_work_ids'],
                            releases_json
                        ))
                        saved += 1
                    except Exception as e:
                        logger.error(f"Error saving orphan: {e}")
                        self.stats['errors'] += 1

                db.commit()

        self.stats['orphans_inserted'] += saved
        return saved

    def enrich_with_spotify(self, song: Dict) -> int:
        """Enrich orphan recordings with Spotify matches (release-aware)"""
        song_id = song['id']
        song_title = song['title']

        logger.info(f"Enriching orphans with Spotify for: {song_title}")

        # Get orphans that need Spotify matching, including their releases
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT id, mb_recording_id, mb_recording_title, mb_artist_credit,
                           mb_first_release_date, mb_releases
                    FROM orphan_recordings
                    WHERE song_id = %s
                      AND (spotify_track_id IS NULL OR %s)
                    ORDER BY mb_artist_credit
                """, (song_id, self.force_refresh))

                orphans = [dict(row) for row in cur.fetchall()]

        if not orphans:
            logger.info(f"  No orphans need Spotify enrichment")
            return 0

        logger.info(f"  Enriching {len(orphans)} orphans")

        matcher = self.get_spotify_matcher()
        enriched = 0

        for orphan in orphans:
            try:
                # Get releases for this orphan (may be JSON string or dict)
                releases = orphan.get('mb_releases') or []
                if isinstance(releases, str):
                    import json
                    releases = json.loads(releases)

                result = self._match_spotify_with_releases(
                    matcher,
                    song_title,
                    orphan['mb_artist_credit'],
                    releases
                )

                if result:
                    self._save_spotify_match(orphan['id'], result)
                    enriched += 1
                    self.stats['spotify_matches'] += 1
                    conf = result['confidence']
                    matched_release = result.get('matched_mb_release_title', 'no release match')
                    logger.info(f"    MATCH ({conf}): {orphan['mb_artist_credit']} -> {result['album_name']} [{matched_release}]")
                else:
                    self._save_spotify_no_match(orphan['id'])
                    self.stats['spotify_no_match'] += 1
                    logger.debug(f"    NO MATCH: {orphan['mb_artist_credit']}")

                # Rate limiting
                time.sleep(0.3)

            except Exception as e:
                logger.error(f"Error enriching orphan: {e}")
                self.stats['errors'] += 1

        return enriched

    def _match_spotify_with_releases(self, matcher: SpotifyMatcher, song_title: str,
                                      artist_credit: str, mb_releases: List[Dict]) -> Optional[Dict]:
        """Try to find a Spotify match, checking against known MB releases"""
        try:
            token = matcher.client.get_spotify_auth_token()
            if not token:
                return None

            artist_name = artist_credit.split("/")[0].strip()

            # Search Spotify for tracks by this artist with this title
            query = f'track:"{song_title}" artist:"{artist_name}"'

            response = matcher.client._make_api_request(
                'get',
                'https://api.spotify.com/v1/search',
                headers={'Authorization': f'Bearer {token}'},
                params={
                    'q': query,
                    'type': 'track',
                    'limit': 20  # Get more results to find release matches
                },
                timeout=10
            )

            if response.status_code != 200:
                return None

            data = response.json()
            tracks = data.get('tracks', {}).get('items', [])

            if not tracks:
                # Try broader search
                query = f'"{song_title}" "{artist_name}"'
                response = matcher.client._make_api_request(
                    'get',
                    'https://api.spotify.com/v1/search',
                    headers={'Authorization': f'Bearer {token}'},
                    params={
                        'q': query,
                        'type': 'track',
                        'limit': 20
                    },
                    timeout=10
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])

            if not tracks:
                return None

            # Normalize MB release titles for comparison
            normalized_mb_releases = {}
            for rel in mb_releases:
                normalized = normalize_for_comparison(rel.get('title', ''))
                normalized_mb_releases[normalized] = rel

            normalized_artist = normalize_for_comparison(artist_name)
            normalized_title = normalize_for_comparison(song_title)

            best_match = None
            best_score = 0
            best_release_match = None

            for track in tracks:
                track_title = track.get('name', '')
                track_artists = ' / '.join([a['name'] for a in track.get('artists', [])])
                spotify_album = track.get('album', {}).get('name', '')

                title_sim = calculate_similarity(normalized_title, normalize_for_comparison(track_title))
                artist_sim = calculate_similarity(normalized_artist, normalize_for_comparison(track_artists.split('/')[0].strip()))

                # Check if Spotify album matches any MB release
                normalized_spotify_album = normalize_for_comparison(spotify_album)
                release_match = None
                album_match_score = 0

                for norm_rel_title, rel_data in normalized_mb_releases.items():
                    sim = calculate_similarity(normalized_spotify_album, norm_rel_title)
                    if sim > album_match_score:
                        album_match_score = sim
                        if sim >= 70:  # Good album match
                            release_match = rel_data

                # Calculate overall score
                # If we have a release match, boost the score significantly
                base_score = (title_sim * 0.3) + (artist_sim * 0.4) + (album_match_score * 0.3)

                # Determine confidence based on release matching
                if release_match and album_match_score >= 85:
                    confidence = 'high'  # Album matches a MB release closely
                elif release_match and album_match_score >= 70:
                    confidence = 'medium'  # Album somewhat matches
                elif artist_sim >= 80 and title_sim >= 80:
                    confidence = 'low'  # Good artist/title match but no release match
                else:
                    confidence = 'none'

                # Only consider if artist matches reasonably
                if artist_sim >= 60 and base_score > best_score:
                    best_score = base_score
                    best_release_match = release_match
                    best_match = {
                        'track_id': track['id'],
                        'track_name': track['name'],
                        'artist_name': track_artists,
                        'album_name': spotify_album,
                        'album_id': track.get('album', {}).get('id', ''),
                        'preview_url': track.get('preview_url'),
                        'external_url': track.get('external_urls', {}).get('spotify'),
                        'album_art_url': self._get_album_art(track),
                        'confidence': confidence,
                        'score': base_score,
                        'album_match_score': album_match_score,
                        'matched_mb_release_id': release_match.get('id') if release_match else None,
                        'matched_mb_release_title': release_match.get('title') if release_match else None
                    }

            return best_match

        except Exception as e:
            logger.debug(f"Spotify search error: {e}")
            return None

    def _get_album_art(self, track: Dict) -> Optional[str]:
        """Extract album art URL from track"""
        images = track.get('album', {}).get('images', [])
        if images:
            # Prefer medium size (300x300)
            for img in images:
                if img.get('height') == 300:
                    return img['url']
            # Fall back to first image
            return images[0]['url']
        return None

    def _save_spotify_match(self, orphan_id: str, match: Dict):
        """Save Spotify match to database"""
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE orphan_recordings SET
                        spotify_track_id = %s,
                        spotify_track_name = %s,
                        spotify_artist_name = %s,
                        spotify_album_name = %s,
                        spotify_album_id = %s,
                        spotify_preview_url = %s,
                        spotify_external_url = %s,
                        spotify_album_art_url = %s,
                        spotify_match_confidence = %s,
                        spotify_match_score = %s,
                        spotify_matched_mb_release_id = %s,
                        spotify_matched_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    match['track_id'],
                    match['track_name'],
                    match['artist_name'],
                    match['album_name'],
                    match['album_id'],
                    match['preview_url'],
                    match['external_url'],
                    match['album_art_url'],
                    match['confidence'],
                    match['score'],
                    match.get('matched_mb_release_id'),
                    orphan_id
                ))
                db.commit()

    def _save_spotify_no_match(self, orphan_id: str):
        """Mark orphan as having no Spotify match"""
        with get_db_connection() as db:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE orphan_recordings SET
                        spotify_match_confidence = 'none',
                        spotify_matched_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (orphan_id,))
                db.commit()

    def run_discover(self, name_filter: Optional[str] = None, limit: Optional[int] = None):
        """Run discovery phase"""
        songs = self.get_songs(name_filter=name_filter, limit=limit)
        if not songs:
            logger.info("No songs found")
            return

        logger.info(f"Discovering orphans for {len(songs)} songs")

        for song in songs:
            self.stats['songs_processed'] += 1
            orphans = self.discover_orphans(song)
            if orphans:
                saved = self.save_orphans(orphans)
                logger.info(f"  Saved {saved} orphans")
            time.sleep(0.5)

        self._print_stats()

    def run_enrich(self, name_filter: Optional[str] = None, limit: Optional[int] = None):
        """Run enrichment phase"""
        songs = self.get_songs(name_filter=name_filter, limit=limit)
        if not songs:
            logger.info("No songs found")
            return

        logger.info(f"Enriching orphans for {len(songs)} songs")

        for song in songs:
            self.stats['songs_processed'] += 1
            self.enrich_with_spotify(song)

        self._print_stats()

    def run_both(self, name_filter: Optional[str] = None, limit: Optional[int] = None):
        """Run both discovery and enrichment"""
        songs = self.get_songs(name_filter=name_filter, limit=limit)
        if not songs:
            logger.info("No songs found")
            return

        logger.info(f"Processing {len(songs)} songs (discover + enrich)")

        for song in songs:
            self.stats['songs_processed'] += 1

            # Discover
            orphans = self.discover_orphans(song)
            if orphans:
                saved = self.save_orphans(orphans)
                logger.info(f"  Saved {saved} orphans")

            # Enrich
            self.enrich_with_spotify(song)

            time.sleep(0.5)

        self._print_stats()

    def _print_stats(self):
        """Print statistics"""
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Songs processed:      {self.stats['songs_processed']}")
        logger.info(f"Orphans discovered:   {self.stats['orphans_discovered']}")
        logger.info(f"Orphans saved:        {self.stats['orphans_inserted']}")
        logger.info(f"Spotify matches:      {self.stats['spotify_matches']}")
        logger.info(f"Spotify no match:     {self.stats['spotify_no_match']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Manage orphan recordings')
    parser.add_argument('action', choices=['discover', 'enrich', 'both'],
                        help='Action to perform')
    parser.add_argument('--name', help='Filter by song name')
    parser.add_argument('--limit', type=int, help='Limit number of songs')
    parser.add_argument('--debug', action='store_true', help='Debug logging')
    parser.add_argument('--force-refresh', action='store_true', help='Bypass cache')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    manager = OrphanManager(force_refresh=args.force_refresh)

    if args.action == 'discover':
        manager.run_discover(name_filter=args.name, limit=args.limit)
    elif args.action == 'enrich':
        manager.run_enrich(name_filter=args.name, limit=args.limit)
    elif args.action == 'both':
        manager.run_both(name_filter=args.name, limit=args.limit)


if __name__ == '__main__':
    main()
