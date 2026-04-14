#!/usr/bin/env python3
"""
Backfill missing release imagery (one-off).

Re-checks Cover Art Archive for every release that has ``cover_art_checked_at``
set but no rows in ``release_imagery``. Prior to the fix for GH #131, a failed
CAA request (5xx, parse error, etc.) was indistinguishable from a legitimate
"no art available" result, and both stamped ``cover_art_checked_at`` — leaving
failed-fetch releases invisible to the ``import_caa_images --all`` backfill
(which filters on ``cover_art_checked_at IS NULL``).

This script closes that gap by:
  1. Selecting releases with ``cover_art_checked_at IS NOT NULL`` and no
     ``release_imagery`` rows (optionally within a date window).
  2. Re-querying CAA for each (``force_refresh=True`` to bypass any cached
     no-art entries that might pre-date the fix).
  3. Saving any imagery returned via the shared ``save_release_imagery()``
     helper, which also refreshes ``cover_art_checked_at``.

Genuine no-art releases are safely idempotent — they re-stamp the timestamp
with no imagery inserted. Releases that now return art are rescued.

Examples:
  # Dry run — show what would be processed, make no DB or API changes
  python backfill_missing_imagery.py --dry-run --limit 20

  # Re-check everything (brute force, ~500ms per release)
  python backfill_missing_imagery.py

  # Only releases checked in the last 60 days
  python backfill_missing_imagery.py --since 60

  # Cap the run for a first pass
  python backfill_missing_imagery.py --limit 500
"""

import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from caa_utils import CoverArtArchiveClient, CoverArtArchiveError
from caa_release_importer import save_release_imagery


def _fetch_candidates(since_days: Optional[int], limit: Optional[int]) -> List[Dict[str, Any]]:
    """Return release rows needing re-check, ordered oldest-checked first."""
    clauses = [
        "r.cover_art_checked_at IS NOT NULL",
        "r.musicbrainz_release_id IS NOT NULL",
        "NOT EXISTS (SELECT 1 FROM release_imagery ri WHERE ri.release_id = r.id)",
    ]
    params: List[Any] = []

    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        clauses.append("r.cover_art_checked_at >= %s")
        params.append(cutoff)

    sql = f"""
        SELECT r.id, r.musicbrainz_release_id, r.title, r.cover_art_checked_at
        FROM releases r
        WHERE {' AND '.join(clauses)}
        ORDER BY r.cover_art_checked_at ASC
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _process_release(
    client: CoverArtArchiveClient,
    release: Dict[str, Any],
    dry_run: bool,
    logger,
) -> Dict[str, int]:
    """Re-check a single release. Returns a dict of per-release stat deltas."""
    delta = {
        'processed': 0,
        'rescued': 0,        # now has art (previously didn't)
        'no_art': 0,         # legitimately no art; re-stamped
        'api_errors': 0,     # CAA still failing; leave cover_art_checked_at alone
        'images_created': 0,
    }

    release_id = release['id']
    mb_release_id = release['musicbrainz_release_id']
    title = (release.get('title') or '<unknown>')[:60]

    try:
        imagery_data = client.extract_imagery_data(mb_release_id)
    except CoverArtArchiveError as e:
        logger.warning(f"  CAA error for {title}: {e}")
        delta['api_errors'] = 1
        return delta

    # Dedupe to one Front, one Back (consistent with mb_release_importer)
    images_to_store: List[Dict[str, Any]] = []
    stored_types = set()
    for img in (imagery_data or []):
        if img['type'] not in stored_types:
            images_to_store.append(img)
            stored_types.add(img['type'])

    delta['processed'] = 1
    if images_to_store:
        delta['rescued'] = 1
        front = sum(1 for i in images_to_store if i['type'] == 'Front')
        back = sum(1 for i in images_to_store if i['type'] == 'Back')
        logger.info(f"  ✓ Rescued {title}: {front} front, {back} back")
    else:
        delta['no_art'] = 1
        logger.debug(f"  = No art for {title} (re-stamped)")

    if dry_run:
        delta['images_created'] = len(images_to_store)
        return delta

    with get_db_connection() as conn:
        result = save_release_imagery(
            conn, release_id, images_to_store,
            logger=logger,
            update_checked_timestamp=True,
        )
        conn.commit()
        delta['images_created'] = result.get('created', 0)

    return delta


def main() -> bool:
    script = ScriptBase(
        name="backfill_missing_imagery",
        description="Re-check CAA for releases whose cover_art_checked_at is set but release_imagery is empty (one-off for GH #131 recovery)",
        epilog=__doc__ or "",
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.parser.add_argument(
        '--since', type=int, default=None, metavar='DAYS',
        help='Only consider releases checked within the last N days. Default: all history.',
    )
    script.parser.add_argument(
        '--limit', type=int, default=None, metavar='N',
        help='Cap the number of releases processed. Default: no cap.',
    )
    args = script.parse_args()

    script.print_header({"DRY RUN": args.dry_run})
    script.logger.info(
        f"Window: {f'last {args.since} days' if args.since is not None else 'all history'}"
    )
    script.logger.info(
        f"Limit: {args.limit if args.limit is not None else 'no cap'}"
    )
    script.logger.info("")

    releases = _fetch_candidates(args.since, args.limit)
    total = len(releases)

    if total == 0:
        script.logger.info("No candidate releases found. Nothing to do.")
        return True

    script.logger.info(f"Found {total} releases to re-check")

    # force_refresh=True so any cached negatives from the pre-fix era are ignored.
    client = CoverArtArchiveClient(force_refresh=True)

    totals = {
        'processed': 0,
        'rescued': 0,
        'no_art': 0,
        'api_errors': 0,
        'images_created': 0,
    }

    # Log ~20 progress lines per run regardless of size, always the first/last.
    progress_every = max(1, total // 20)

    for idx, release in enumerate(releases, 1):
        is_progress_tick = (
            args.debug
            or idx == 1
            or idx == total
            or idx % progress_every == 0
        )
        if is_progress_tick:
            script.logger.info(
                f"[{idx}/{total}] rescued={totals['rescued']} "
                f"no_art={totals['no_art']} errors={totals['api_errors']} — "
                f"{(release['title'] or '<unknown>')[:60]}"
            )
        try:
            delta = _process_release(client, release, args.dry_run, script.logger)
            for k, v in delta.items():
                totals[k] += v
        except KeyboardInterrupt:
            script.logger.warning("Interrupted by user — stopping early.")
            break
        except Exception as e:  # pragma: no cover — safety net
            script.logger.error(
                f"  Unexpected error on release {release['id']}: {e}",
                exc_info=args.debug,
            )
            totals['api_errors'] += 1

    script.print_section("Results", {
        "Candidates found": total,
        "Processed": totals['processed'],
        "Rescued (now has art)": totals['rescued'],
        "Confirmed no art": totals['no_art'],
        "CAA errors (left unstamped)": totals['api_errors'],
        "Images created": totals['images_created'],
    })

    caa_stats = client.get_stats()
    script.print_section("CAA Client", {
        "API calls": caa_stats['api_calls'],
        "Cache hits": caa_stats['cache_hits'],
    })

    # Non-zero api_errors is informational, not a failure.
    return True


if __name__ == "__main__":
    run_script(main)
