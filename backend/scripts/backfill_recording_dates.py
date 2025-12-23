#!/usr/bin/env python3
"""
Backfill Recording Dates from MusicBrainz Cache

Re-processes existing recordings to extract proper recording dates from
cached MusicBrainz data using the new date extraction logic.

This script:
1. Finds recordings with musicbrainz_id that need date backfill
2. Loads cached MusicBrainz recording data
3. Extracts recording dates from performer relations or first-release-date
4. Updates recordings with the new date fields

Run after applying migration 001_add_recording_date_tracking.sql
"""

from script_base import ScriptBase, run_script
from mb_release_importer import extract_recording_date_from_mb
from mb_utils import MusicBrainzSearcher
from db_utils import get_db_connection, find_song_by_name_or_id


def main() -> bool:
    script = ScriptBase(
        name="backfill_recording_dates",
        description="Backfill recording dates from cached MusicBrainz data",
        epilog="""
Examples:
  # Dry run to see what would be updated
  python backfill_recording_dates.py --dry-run

  # Actually update recordings
  python backfill_recording_dates.py

  # Backfill for a specific song (always processes all recordings)
  python backfill_recording_dates.py --name "Black Velvet" --dry-run

  # Limit to first 100 recordings
  python backfill_recording_dates.py --limit 100 --dry-run

  # Force re-process even if already has a source
  python backfill_recording_dates.py --force

  # Debug to see date extraction details
  python backfill_recording_dates.py --debug --limit 10
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=10000)

    script.parser.add_argument(
        '--name',
        help='Song name - backfill only recordings for this song (implies --force)'
    )

    script.parser.add_argument(
        '--force',
        action='store_true',
        help='Re-process recordings even if they already have a recording_date_source'
    )

    script.parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Commit after this many updates (default: 100)'
    )

    args = script.parse_args()

    # --name implies --force for that song
    force_mode = args.force or args.name is not None
    song_filter = None

    # Look up song if --name provided
    if args.name:
        song_filter = find_song_by_name_or_id(name=args.name)
        if not song_filter:
            script.logger.error(f"Song not found: {args.name}")
            return False
        script.logger.info(f"Filtering to song: {song_filter['title']} (ID: {song_filter['id']})")

    script.print_header({
        "DRY RUN": args.dry_run,
        "FORCE": force_mode,
        "SONG FILTER": args.name is not None,
    })

    # Initialize MusicBrainz searcher for cache access
    mb_searcher = MusicBrainzSearcher()

    # Stats tracking
    stats = {
        'total_candidates': 0,
        'cache_found': 0,
        'cache_missing': 0,
        'updated_from_performer_relation': 0,
        'updated_from_first_release': 0,
        'no_date_available': 0,
        'skipped_already_has_source': 0,
        'errors': 0,
        'commits': 0,
    }

    # Batch commit tracking
    updates_in_batch = 0

    # Find recordings that need backfill
    script.logger.info("Finding recordings to backfill...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if song_filter:
                # Process all recordings for this specific song
                cur.execute("""
                    SELECT r.id, r.musicbrainz_id, def_rel.title as album_title, r.recording_year,
                           r.recording_date, r.recording_date_source
                    FROM recordings r
                    LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                    WHERE r.musicbrainz_id IS NOT NULL
                      AND r.song_id = %s
                    ORDER BY r.created_at DESC
                    LIMIT %s
                """, (song_filter['id'], args.limit))
            elif force_mode:
                # Process all recordings with MB ID
                cur.execute("""
                    SELECT r.id, r.musicbrainz_id, def_rel.title as album_title, r.recording_year,
                           r.recording_date, r.recording_date_source
                    FROM recordings r
                    LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                    WHERE r.musicbrainz_id IS NOT NULL
                    ORDER BY r.created_at DESC
                    LIMIT %s
                """, (args.limit,))
            else:
                # Only process recordings without a source or with legacy source
                cur.execute("""
                    SELECT r.id, r.musicbrainz_id, def_rel.title as album_title, r.recording_year,
                           r.recording_date, r.recording_date_source
                    FROM recordings r
                    LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                    WHERE r.musicbrainz_id IS NOT NULL
                      AND (r.recording_date_source IS NULL
                           OR r.recording_date_source = 'legacy_release_date')
                    ORDER BY r.created_at DESC
                    LIMIT %s
                """, (args.limit,))

            recordings = cur.fetchall()
            stats['total_candidates'] = len(recordings)

            script.logger.info(f"Found {len(recordings)} recordings to process")

            for i, recording in enumerate(recordings, 1):
                recording_id = recording['id']
                mb_id = recording['musicbrainz_id']
                album_title = recording['album_title'] or 'Unknown'
                current_source = recording['recording_date_source']

                if current_source and current_source != 'legacy_release_date' and not force_mode:
                    stats['skipped_already_has_source'] += 1
                    continue

                # Load cached MusicBrainz data
                mb_data = mb_searcher.get_recording_details(mb_id)

                if not mb_data:
                    stats['cache_missing'] += 1
                    script.logger.debug(f"  [{i}] No cache for: {album_title[:40]} ({mb_id})")
                    continue

                stats['cache_found'] += 1

                # Extract date using new logic
                date_info = extract_recording_date_from_mb(mb_data, logger=script.logger)

                source = date_info.get('recording_date_source')
                year = date_info.get('recording_year')
                date = date_info.get('recording_date')
                precision = date_info.get('recording_date_precision')
                mb_first_release = date_info.get('mb_first_release_date')

                if source:
                    if source == 'mb_performer_relation':
                        stats['updated_from_performer_relation'] += 1
                    else:
                        stats['updated_from_first_release'] += 1

                    script.logger.info(
                        f"  [{i}/{len(recordings)}] {album_title[:40]}: "
                        f"year={year}, source={source}, precision={precision}"
                    )

                    if not args.dry_run:
                        cur.execute("""
                            UPDATE recordings
                            SET recording_date = %s,
                                recording_year = %s,
                                recording_date_source = %s,
                                recording_date_precision = %s,
                                mb_first_release_date = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (
                            date,
                            year,
                            source,
                            precision,
                            mb_first_release,
                            recording_id
                        ))
                        updates_in_batch += 1
                else:
                    stats['no_date_available'] += 1
                    # Still update mb_first_release_date if available
                    if mb_first_release and not args.dry_run:
                        cur.execute("""
                            UPDATE recordings
                            SET mb_first_release_date = %s,
                                recording_date_source = 'none_available',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (mb_first_release, recording_id))
                        updates_in_batch += 1

                    script.logger.debug(
                        f"  [{i}] No date found: {album_title[:40]}"
                    )

                # Batch commit
                if not args.dry_run and updates_in_batch >= args.batch_size:
                    conn.commit()
                    stats['commits'] += 1
                    script.logger.info(f"  -- Committed batch ({updates_in_batch} updates, total commits: {stats['commits']})")
                    updates_in_batch = 0

            # Final commit for remaining updates
            if not args.dry_run and updates_in_batch > 0:
                conn.commit()
                stats['commits'] += 1
                script.logger.info(f"Final commit ({updates_in_batch} updates)")

    # Print summary
    script.logger.info("")
    script.print_summary({
        "Total candidates": stats['total_candidates'],
        "Cache found": stats['cache_found'],
        "Cache missing": stats['cache_missing'],
        "Updated (performer relation)": stats['updated_from_performer_relation'],
        "Updated (first release)": stats['updated_from_first_release'],
        "No date available": stats['no_date_available'],
        "Skipped (already has source)": stats['skipped_already_has_source'],
        "Commits": stats['commits'],
        "Errors": stats['errors'],
    }, title="BACKFILL SUMMARY")

    # Log effectiveness
    if stats['cache_found'] > 0:
        performer_pct = (stats['updated_from_performer_relation'] / stats['cache_found']) * 100
        first_release_pct = (stats['updated_from_first_release'] / stats['cache_found']) * 100
        no_date_pct = (stats['no_date_available'] / stats['cache_found']) * 100

        script.logger.info("")
        script.logger.info("Date source breakdown (of recordings with cache):")
        script.logger.info(f"  Performer relations: {performer_pct:.1f}%")
        script.logger.info(f"  First release date:  {first_release_pct:.1f}%")
        script.logger.info(f"  No date available:   {no_date_pct:.1f}%")

    return True


if __name__ == "__main__":
    run_script(main)
