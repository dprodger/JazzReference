#!/usr/bin/env python3
"""
Backfill recording leaders from MusicBrainz artist-credit (one-off).

Context
-------
A scan against production found ~1,650 recordings with no row in
``recording_performers`` at ``role='leader'``. Sampling showed a clean
pattern: these are mostly pop/crossover tracks where MusicBrainz carries
only producer/engineer/arranger relations (which the importer stores
as ``role='other'``) and the billed artist lives solely in the MB
recording's ``artist-credit`` field — never as a performance relation.
Because ``_ensure_leader_exists`` promotes the first non-other performer
to leader and skips ``role='other'`` rows, these recordings end up with
zero leaders.

The fix on the importer side (``_ensure_leader_from_artist_credit`` in
``integrations/musicbrainz/performer_importer.py``) synthesizes a leader
row from artist-credit when the normal ingest leaves none. This script
runs the same helper against every affected existing recording.

Behaviour
---------
For each candidate recording (no leader, has ``musicbrainz_id``):

  1. Fetch the recording from MB via the cached ``MusicBrainzSearcher``
     (warm cache -> no API call; cold cache -> one rate-limited call).
  2. Call ``_ensure_leader_from_artist_credit`` in a fresh per-iteration
     DB connection (long-lived connections get reaped by Supabase).
  3. Commit. On failure, the connection rolls back — the recording
     simply stays leaderless and a future run will retry.

Recordings with no ``musicbrainz_id`` are reported but skipped; there's
nothing to fall back to for them without more research.

Examples
--------
    # Dry run — scan candidates + preview synthesized leaders, no DB writes
    python backfill_recording_leaders.py --dry-run --limit 20

    # First cautious batch, then everything
    python backfill_recording_leaders.py --limit 200
    python backfill_recording_leaders.py

    # Scope to a single song (handy for spot-checking)
    python backfill_recording_leaders.py --song-id 22dc9fbe-3839-4830-8b92-b6659128cc20
"""

import sys
from typing import List, Dict, Any, Optional

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from integrations.musicbrainz.utils import MusicBrainzSearcher
from integrations.musicbrainz.performer_importer import PerformerImporter


def _fetch_candidates(song_id: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    """
    Return leaderless recording rows, ordered oldest first for stable runs.

    A recording is a candidate when:
      - It has no row in ``recording_performers`` with ``role='leader'``.
      - It has a ``musicbrainz_id`` (we need one to fetch artist-credit).

    With ``--song-id``, restrict to recordings of that song.
    """
    clauses = [
        "r.musicbrainz_id IS NOT NULL",
        """NOT EXISTS (
            SELECT 1 FROM recording_performers rp
            WHERE rp.recording_id = r.id AND rp.role = 'leader'
        )""",
    ]
    params: List[Any] = []

    if song_id:
        clauses.append("r.song_id = %s")
        params.append(song_id)

    sql = f"""
        SELECT r.id, r.musicbrainz_id, r.title, s.title AS song_title
        FROM recordings r
        JOIN songs s ON s.id = r.song_id
        WHERE {' AND '.join(clauses)}
        ORDER BY s.title, r.id
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _process_recording(
    searcher: MusicBrainzSearcher,
    importer: PerformerImporter,
    recording: Dict[str, Any],
    dry_run: bool,
    logger,
) -> Dict[str, int]:
    """Process one recording. Returns per-recording stat deltas."""
    delta = {
        'processed': 0,
        'rescued': 0,         # got a leader synthesized
        'no_credit': 0,       # MB returned a recording with empty artist-credit
        'mb_not_found': 0,    # MB 404 or fetch error
        'already_leader': 0,  # race: a leader appeared since candidate list
    }

    delta['processed'] = 1
    recording_id = recording['id']
    mb_id = recording['musicbrainz_id']
    label = f"{recording.get('song_title') or '?'}/{(recording.get('title') or '?')[:50]}"

    recording_data = searcher.get_recording_details(mb_id)
    if not recording_data:
        logger.debug(f"  MB not found for {label}")
        delta['mb_not_found'] = 1
        return delta

    artist_credits = recording_data.get('artist-credit') or []
    if not artist_credits:
        logger.debug(f"  No artist-credit for {label}")
        delta['no_credit'] = 1
        return delta

    if dry_run:
        # Preview without touching the DB.
        artists = importer.parse_artist_credits(artist_credits)
        names = ', '.join(a['name'] for a in artists if a.get('name')) or '<none>'
        logger.info(f"  [DRY RUN] {label} -> would add leader: {names}")
        delta['rescued'] = 1
        return delta

    # Fresh per-iteration connection so long runs survive idle-timeouts.
    with get_db_connection() as conn:
        inserted = importer._ensure_leader_from_artist_credit(
            conn, recording_id, recording_data
        )
        conn.commit()

    if inserted > 0:
        names = ', '.join(
            a['name'] for a in importer.parse_artist_credits(artist_credits)
            if a.get('name')
        )
        logger.info(f"  ✓ {label} -> {names}")
        delta['rescued'] = 1
    else:
        # Either already had a leader by the time we got here, or every
        # artist-credit entry was unusable (no name). Treat as a no-op.
        delta['already_leader'] = 1

    return delta


def main() -> bool:
    script = ScriptBase(
        name="backfill_recording_leaders",
        description="Synthesize missing recording leaders from MusicBrainz artist-credit",
        epilog=__doc__ or "",
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.parser.add_argument(
        '--limit', type=int, default=None, metavar='N',
        help='Cap the number of recordings processed. Default: no cap.',
    )
    script.parser.add_argument(
        '--song-id', type=str, default=None, metavar='UUID',
        help='Restrict to recordings of a single song (handy for spot-checks).',
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

    recordings = _fetch_candidates(args.song_id, args.limit)
    total = len(recordings)

    if total == 0:
        script.logger.info("No candidate recordings found. Nothing to do.")
        return True

    script.logger.info(f"Found {total} leaderless recordings with a MusicBrainz id")

    searcher = MusicBrainzSearcher()
    # We only use ``_ensure_leader_from_artist_credit`` and
    # ``parse_artist_credits`` — no need to pass a real db connection or
    # rate limiter into the importer itself.
    importer = PerformerImporter(dry_run=False)

    totals = {
        'processed': 0,
        'rescued': 0,
        'no_credit': 0,
        'mb_not_found': 0,
        'already_leader': 0,
    }

    progress_every = max(1, total // 20)

    for idx, recording in enumerate(recordings, 1):
        is_progress_tick = (
            args.debug
            or idx == 1
            or idx == total
            or idx % progress_every == 0
        )
        if is_progress_tick:
            script.logger.info(
                f"[{idx}/{total}] rescued={totals['rescued']} "
                f"no_credit={totals['no_credit']} mb404={totals['mb_not_found']} — "
                f"{(recording.get('song_title') or '?')[:40]}"
            )
        try:
            delta = _process_recording(
                searcher, importer, recording, args.dry_run, script.logger
            )
            for k, v in delta.items():
                totals[k] += v
        except KeyboardInterrupt:
            script.logger.warning("Interrupted by user — stopping early.")
            break
        except Exception as e:  # pragma: no cover — safety net
            script.logger.error(
                f"  Unexpected error on recording {recording['id']}: {e}",
                exc_info=args.debug,
            )

    script.print_section("Results", {
        "Candidates found": total,
        "Processed": totals['processed'],
        "Leaders synthesized": totals['rescued'],
        "MB artist-credit empty": totals['no_credit'],
        "MB recording not found": totals['mb_not_found'],
        "Already had leader (race)": totals['already_leader'],
    })

    mb_stats = getattr(searcher, 'get_stats', lambda: {})()
    if mb_stats:
        script.print_section("MusicBrainz Client", {
            "API calls": mb_stats.get('api_calls', '?'),
            "Cache hits": mb_stats.get('cache_hits', '?'),
        })

    return True


if __name__ == "__main__":
    run_script(main)
