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
from mb_utils import MusicBrainzSearcher


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
    script.add_limit_arg(default=100)

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
        'tracks_title_same': 0,
        'mb_api_calls': 0,
        'errors': 0,
    }

    # Find releases that have MB release IDs and recording_releases without track_title
    script.logger.info("Finding releases with recording_releases missing track_title...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT
                    rel.id AS release_id,
                    rel.musicbrainz_release_id AS mb_release_id,
                    rel.title AS release_title
                FROM releases rel
                JOIN recording_releases rr ON rr.release_id = rel.id
                WHERE rel.musicbrainz_release_id IS NOT NULL
                  AND rr.track_title IS NULL
                ORDER BY rel.title
                LIMIT %s
            """, (args.limit,))
            releases = cur.fetchall()

    stats['releases_found'] = len(releases)
    script.logger.info(f"Found {len(releases)} releases to process")
    script.logger.info("")

    if not releases:
        script.print_summary(stats)
        return True

    mb_searcher = MusicBrainzSearcher()

    for i, release in enumerate(releases, 1):
        release_id = release['release_id']
        mb_release_id = release['mb_release_id']
        release_title = release['release_title']

        script.logger.info(f"[{i}/{len(releases)}] {release_title} (MB: {mb_release_id})")

        try:
            # Fetch release details from MusicBrainz
            release_data = mb_searcher.get_release_details(mb_release_id)
            stats['mb_api_calls'] += 1

            if not release_data:
                script.logger.warning(f"  Could not fetch release details from MB")
                stats['errors'] += 1
                continue

            # Build a map of MB recording ID → track title from the release
            mb_track_map = {}
            for medium in release_data.get('media', []):
                for track in medium.get('tracks', []):
                    recording = track.get('recording', {})
                    recording_id = recording.get('id')
                    if recording_id:
                        mb_track_map[recording_id] = track.get('title', '')

            script.logger.debug(f"  MB release has {len(mb_track_map)} tracks")

            # Get our recording_releases for this release
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT rr.id, rr.track_title, rec.musicbrainz_id AS mb_recording_id,
                               rec.title AS recording_title
                        FROM recording_releases rr
                        JOIN recordings rec ON rr.recording_id = rec.id
                        WHERE rr.release_id = %s
                    """, (release_id,))
                    recording_releases = cur.fetchall()

            updates = []
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
                    script.logger.debug(
                        f"  Recording {mb_recording_id} not found in MB release tracklist")
                    stats['tracks_no_mb_match'] += 1
                    continue

                # Only set if it differs from the recording title (otherwise it's redundant)
                if mb_track_title == rr['recording_title']:
                    stats['tracks_title_same'] += 1
                    continue

                updates.append((mb_track_title, rr['id']))
                script.logger.debug(
                    f"  '{rr['recording_title']}' → '{mb_track_title}' on this release")

            if updates and not args.dry_run:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.executemany("""
                            UPDATE recording_releases
                            SET track_title = %s
                            WHERE id = %s
                        """, updates)
                    conn.commit()

            stats['tracks_updated'] += len(updates)
            stats['releases_processed'] += 1
            if updates:
                script.logger.info(f"  Updated {len(updates)} track title(s)")

        except Exception as e:
            script.logger.error(f"  Error: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
