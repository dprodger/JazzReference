#!/usr/bin/env python3
"""
Dedupe recording_performers leader rows created by the v1 leader backfill.

Context
-------
The first cut of ``_ensure_leader_from_artist_credit`` (see commit that
introduced it) inserted a fresh ``role='leader'`` row for every artist
in a recording's MB artist-credit whenever no leader existed — without
checking whether that person already had a row on the recording with a
different role. That produced duplicates for the common case where the
billed artist also produced the session (Ron Carter on his own dates is
the canonical example): one ``role='other'`` row from the producer
relation, plus one ``role='leader'`` row from the artist-credit
fallback, same performer_id, both with ``instrument_id IS NULL``. The
``UNIQUE (recording_id, performer_id, instrument_id)`` index treats
multiple NULL instrument_ids as distinct, so nothing blocked the
insert.

This script walks the resulting duplicates and collapses them to a
single ``role='leader'`` row per ``(recording_id, performer_id)``,
preferring any row that already has an instrument so we preserve the
credit info.

Scope
-----
Only touches ``(recording_id, performer_id)`` pairs where BOTH:
  - At least one row has ``role='leader'`` AND ``instrument_id IS NULL``
    (the fallback-created row), AND
  - At least one other row exists for the same pair.

This deliberately skips pre-existing duplicates that don't match the
fallback signature (e.g. a performer credited on two different
instruments) — those are out of scope for this one-off.

Behaviour per pair
------------------
  1. Pick the target row to keep: prefer a row with a non-null
     ``instrument_id``; otherwise take the lowest-id row.
  2. ``UPDATE`` the target to ``role='leader'`` (no-op when it already
     is).
  3. ``DELETE`` every other row for the pair.

End state: exactly one ``role='leader'`` row per
``(recording_id, performer_id)``.

Examples
--------
    # Dry run: list affected pairs, make no changes
    python dedupe_leader_rows.py --dry-run --limit 50

    # Fix everything
    python dedupe_leader_rows.py

    # Spot-check on one song
    python dedupe_leader_rows.py --song-id 768016cb-4d45-4400-84a2-d788a7002dd7
"""

import sys
from typing import List, Dict, Any, Optional

from script_base import ScriptBase, run_script
from db_utils import get_db_connection


def _fetch_affected_pairs(song_id: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    """
    Return (recording_id, performer_id) pairs with a fallback-style
    duplicate, each row annotated with enough context to log sensibly.
    """
    clauses = ["""
        EXISTS (
            SELECT 1 FROM recording_performers rp_leader
            WHERE rp_leader.recording_id = rp.recording_id
              AND rp_leader.performer_id = rp.performer_id
              AND rp_leader.role = 'leader'
              AND rp_leader.instrument_id IS NULL
        )
    """]
    params: List[Any] = []

    if song_id:
        clauses.append("rec.song_id = %s")
        params.append(song_id)

    sql = f"""
        SELECT
            rp.recording_id,
            rp.performer_id,
            MIN(p.name) AS performer_name,
            MIN(s.title) AS song_title,
            MIN(rec.title) AS recording_title,
            COUNT(*) AS row_count
        FROM recording_performers rp
        JOIN recordings rec ON rec.id = rp.recording_id
        JOIN songs s ON s.id = rec.song_id
        JOIN performers p ON p.id = rp.performer_id
        WHERE {' AND '.join(clauses)}
        GROUP BY rp.recording_id, rp.performer_id
        HAVING COUNT(*) >= 2
        ORDER BY MIN(s.title), rp.recording_id
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _collapse_pair(
    pair: Dict[str, Any],
    dry_run: bool,
    logger,
) -> Dict[str, int]:
    """Collapse one duplicate pair down to a single leader row."""
    delta = {
        'pairs_processed': 0,
        'pairs_collapsed': 0,
        'rows_deleted': 0,
        'rows_promoted': 0,
    }

    recording_id = pair['recording_id']
    performer_id = pair['performer_id']
    label = (
        f"{pair.get('song_title') or '?'} / "
        f"{(pair.get('recording_title') or '?')[:40]} / "
        f"{pair.get('performer_name') or '?'}"
    )

    delta['pairs_processed'] = 1

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Re-read rows inside the transaction — another process may
            # have raced us since the candidate list was fetched.
            cur.execute("""
                SELECT id, role, instrument_id
                FROM recording_performers
                WHERE recording_id = %s AND performer_id = %s
                ORDER BY (instrument_id IS NULL), id
            """, (recording_id, performer_id))
            rows = cur.fetchall()

            if len(rows) < 2:
                # Raced or already fixed — nothing to collapse.
                logger.debug(f"  Skipping (only {len(rows)} row now): {label}")
                return delta

            # Sort order above puts instrumented rows first, then lowest id.
            target = rows[0]
            losers = rows[1:]
            loser_ids = [r['id'] for r in losers]

            if dry_run:
                target_desc = f"role={target['role']!r} inst={target['instrument_id']}"
                loser_descs = ', '.join(
                    f"role={r['role']!r} inst={r['instrument_id']}"
                    for r in losers
                )
                logger.info(
                    f"  [DRY RUN] {label}: keep id={target['id']} "
                    f"({target_desc}); drop [{loser_descs}]"
                )
                delta['pairs_collapsed'] = 1
                delta['rows_deleted'] = len(losers)
                if target['role'] != 'leader':
                    delta['rows_promoted'] = 1
                return delta

            if target['role'] != 'leader':
                cur.execute("""
                    UPDATE recording_performers
                    SET role = 'leader'
                    WHERE id = %s
                """, (target['id'],))
                delta['rows_promoted'] = 1

            cur.execute("""
                DELETE FROM recording_performers
                WHERE id = ANY(%s)
            """, (loser_ids,))
            delta['rows_deleted'] = cur.rowcount

        conn.commit()

    logger.info(f"  ✓ {label}: collapsed {len(losers) + 1} rows to 1 leader row")
    delta['pairs_collapsed'] = 1
    return delta


def main() -> bool:
    script = ScriptBase(
        name="dedupe_leader_rows",
        description="Collapse fallback-created duplicate leader rows to a single row per (recording, performer).",
        epilog=__doc__ or "",
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.parser.add_argument(
        '--limit', type=int, default=None, metavar='N',
        help='Cap the number of pairs processed. Default: no cap.',
    )
    script.parser.add_argument(
        '--song-id', type=str, default=None, metavar='UUID',
        help='Restrict to recordings of a single song.',
    )
    args = script.parse_args()

    script.print_header({"DRY RUN": args.dry_run})
    script.logger.info(
        f"Scope: {'song ' + args.song_id if args.song_id else 'all songs'}"
    )
    script.logger.info(
        f"Limit: {args.limit if args.limit is not None else 'no cap'}"
    )
    script.logger.info("")

    pairs = _fetch_affected_pairs(args.song_id, args.limit)
    total = len(pairs)

    if total == 0:
        script.logger.info("No duplicate leader pairs found. Nothing to do.")
        return True

    script.logger.info(f"Found {total} (recording, performer) pairs with duplicate rows")

    totals = {
        'pairs_processed': 0,
        'pairs_collapsed': 0,
        'rows_deleted': 0,
        'rows_promoted': 0,
    }

    progress_every = max(1, total // 20)

    for idx, pair in enumerate(pairs, 1):
        is_progress_tick = (
            args.debug
            or idx == 1
            or idx == total
            or idx % progress_every == 0
        )
        if is_progress_tick:
            script.logger.info(
                f"[{idx}/{total}] collapsed={totals['pairs_collapsed']} — "
                f"{(pair.get('song_title') or '?')[:40]}"
            )
        try:
            delta = _collapse_pair(pair, args.dry_run, script.logger)
            for k, v in delta.items():
                totals[k] += v
        except KeyboardInterrupt:
            script.logger.warning("Interrupted by user — stopping early.")
            break
        except Exception as e:  # pragma: no cover — safety net
            script.logger.error(
                f"  Unexpected error on pair "
                f"({pair.get('recording_id')}, {pair.get('performer_id')}): {e}",
                exc_info=args.debug,
            )

    script.print_section("Results", {
        "Pairs found": total,
        "Pairs processed": totals['pairs_processed'],
        "Pairs collapsed": totals['pairs_collapsed'],
        "Rows promoted to leader": totals['rows_promoted'],
        "Rows deleted": totals['rows_deleted'],
    })

    return True


if __name__ == "__main__":
    run_script(main)
