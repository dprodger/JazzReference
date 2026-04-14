#!/usr/bin/env python3
"""
Backfill MusicBrainz Track Titles

Populates recording_releases.track_title with the track title from the
MusicBrainz release (the title as it appears on that specific release,
which may differ from the recording title).

This fetches release details from the MB API and matches tracks by
MusicBrainz recording ID.

Usage:
    python backfill_mb_track_titles.py --limit 100
    python backfill_mb_track_titles.py --limit 100 --dry-run
    python backfill_mb_track_titles.py --debug
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from integrations.musicbrainz.utils import MusicBrainzSearcher


BATCH_SIZE = 500  # Flush DB updates every N releases


def main():
    script = ScriptBase(
        name="backfill_mb_track_titles",
        description="Backfill track titles from MusicBrainz release details",
        epilog="""
Examples:
  python backfill_mb_track_titles.py --limit 100
  python backfill_mb_track_titles.py --limit 100 --dry-run
  python backfill_mb_track_titles.py --limit 1000 --debug
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=10000)

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    stats = {
        'releases_found': 0,
        'releases_processed': 0,
        'tracks_updated': 0,
        'tracks_already_set': 0,
        'tracks_no_mb_match': 0,
        'mb_api_calls': 0,
        'mb_cache_hits': 0,
        'errors': 0,
    }

    # Find releases that have MB release IDs and recording_releases without track_title.
    # Also pre-fetch all the recording_releases we'll need in one query.
    script.logger.info("Finding releases with recording_releases missing track_title...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get distinct releases needing work
            cur.execute("""
                SELECT DISTINCT
                    rel.id AS release_id,
                    rel.musicbrainz_release_id AS mb_release_id,
                    rel.title AS release_title
                FROM releases rel
                JOIN recording_releases rr ON rr.release_id = rel.id
                WHERE rel.musicbrainz_release_id IS NOT NULL
                  AND rr.track_title IS NULL
                LIMIT %s
            """, (args.limit,))
            releases = cur.fetchall()

            if not releases:
                stats['releases_found'] = 0
                script.logger.info("No releases to process")
                script.print_summary(stats)
                return True

            release_ids = [r['release_id'] for r in releases]
            stats['releases_found'] = len(releases)
            script.logger.info(f"Found {len(releases)} releases to process")

            # Pre-fetch ALL recording_releases for these releases in one query
            cur.execute("""
                SELECT rr.id, rr.release_id, rr.track_title,
                       rec.musicbrainz_id AS mb_recording_id,
                       rec.title AS recording_title
                FROM recording_releases rr
                JOIN recordings rec ON rr.recording_id = rec.id
                WHERE rr.release_id = ANY(%s)
            """, (release_ids,))
            all_rrs = cur.fetchall()

    # Index recording_releases by release_id
    rrs_by_release = {}
    for rr in all_rrs:
        rrs_by_release.setdefault(rr['release_id'], []).append(rr)

    script.logger.info(f"Pre-fetched {len(all_rrs)} recording_releases")
    script.logger.info("")

    import time
    start_time = time.time()

    mb_searcher = MusicBrainzSearcher(cache_days=365)
    pending_updates = []  # (track_title, rr_id) tuples

    for i, release in enumerate(releases, 1):
        release_id = release['release_id']
        mb_release_id = release['mb_release_id']
        release_title = release['release_title']

        if i % 1000 == 0 or i == 1:
            script.logger.info(f"[{i}/{len(releases)}] "
                             f"updated: {stats['tracks_updated']}, "
                             f"cache: {stats['mb_cache_hits']}, "
                             f"API: {stats['mb_api_calls']}, "
                             f"errors: {stats['errors']}")

        try:
            # Fetch release details from MusicBrainz (cached or API)
            release_data = mb_searcher.get_release_details(mb_release_id)
            if mb_searcher.last_made_api_call:
                stats['mb_api_calls'] += 1
            else:
                stats['mb_cache_hits'] += 1

            if not release_data:
                script.logger.debug(f"  [{i}] {release_title}: no MB data")
                stats['errors'] += 1
                continue

            # Build a map of MB recording ID -> track title from the release
            mb_track_map = {}
            for medium in release_data.get('media', []):
                for track in medium.get('tracks', []):
                    recording = track.get('recording', {})
                    recording_id = recording.get('id')
                    if recording_id:
                        mb_track_map[recording_id] = track.get('title', '')[:500]

            # Match against our recording_releases
            recording_releases = rrs_by_release.get(release_id, [])
            release_updates = 0

            for rr in recording_releases:
                mb_recording_id = rr['mb_recording_id']
                if not mb_recording_id:
                    stats['tracks_no_mb_match'] += 1
                    continue

                if rr['track_title'] is not None:
                    stats['tracks_already_set'] += 1
                    continue

                mb_track_title = mb_track_map.get(mb_recording_id)
                if not mb_track_title:
                    stats['tracks_no_mb_match'] += 1
                    continue

                pending_updates.append((mb_track_title, rr['id']))
                release_updates += 1

            stats['tracks_updated'] += release_updates
            stats['releases_processed'] += 1

            # Flush batch to DB periodically
            if len(pending_updates) >= BATCH_SIZE and not args.dry_run:
                _flush_updates(pending_updates)
                pending_updates = []

        except Exception as e:
            script.logger.error(f"  [{i}] {release_title}: {e}")
            stats['errors'] += 1

    # Final flush
    if pending_updates and not args.dry_run:
        _flush_updates(pending_updates)

    elapsed = time.time() - start_time
    script.logger.info(f"\nCompleted in {elapsed:.1f}s "
                      f"({stats['releases_processed']} releases, "
                      f"{stats['tracks_updated']} tracks updated, "
                      f"{stats['mb_cache_hits']} cache hits, "
                      f"{stats['mb_api_calls']} API calls)")
    script.print_summary(stats)
    return stats['errors'] == 0


def _flush_updates(updates):
    """Write a batch of (track_title, rr_id) updates to the DB."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                UPDATE recording_releases
                SET track_title = %s
                WHERE id = %s
            """, updates)
        conn.commit()


if __name__ == "__main__":
    run_script(main)
