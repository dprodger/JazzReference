#!/usr/bin/env python3
"""
Populate vocal/instrumental data from performer credits.

This script:
1. Creates (or finds) a "JazzBot" system user for automated contributions
2. Looks at recordings with multiple performers (band credits)
3. If the credits include vocals -> adds a vote for "Vocal" (is_instrumental=False)
4. If no vocals in credits -> adds a vote for "Instrumental" (is_instrumental=True)

These contributions can be overridden by real user votes since they follow
the standard voting/consensus system.

Usage:
    # Dry run - see what would be changed
    python scripts/populate_vocal_instrumental.py --dry-run

    # Run the population
    python scripts/populate_vocal_instrumental.py

    # Limit to first N recordings
    python scripts/populate_vocal_instrumental.py --limit 100
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection

# Bot user configuration
BOT_EMAIL = "jazzbot@approachnote.com"
BOT_DISPLAY_NAME = "JazzBot"


def get_or_create_bot_user(cur, dry_run: bool, logger) -> str:
    """Get or create the JazzBot system user. Returns user ID."""
    cur.execute("SELECT id FROM users WHERE email = %s", (BOT_EMAIL,))
    row = cur.fetchone()

    if row:
        logger.info(f"Found existing bot user: {BOT_EMAIL} (ID: {row['id']})")
        return str(row['id'])

    if dry_run:
        logger.info(f"[DRY RUN] Would create bot user: {BOT_EMAIL}")
        return "dry-run-bot-id"

    # Create the bot user with a placeholder password hash (can't actually be used to log in)
    # The hash is intentionally invalid - not a real bcrypt hash
    fake_password_hash = "$2b$12$BOTUSER.CANNOT.LOGIN.PLACEHOLDER"
    cur.execute("""
        INSERT INTO users (email, email_verified, display_name, is_active, password_hash)
        VALUES (%s, true, %s, true, %s)
        RETURNING id
    """, (BOT_EMAIL, BOT_DISPLAY_NAME, fake_password_hash))
    bot_id = str(cur.fetchone()['id'])
    logger.info(f"Created bot user: {BOT_EMAIL} (ID: {bot_id})")
    return bot_id


def get_recordings_with_credits(cur, limit: int = None):
    """
    Get recordings that have multiple performers (band credits).
    Returns list of (recording_id, has_vocals).
    """
    query = """
        WITH multi_performer_recordings AS (
            SELECT recording_id
            FROM recording_performers
            GROUP BY recording_id
            HAVING COUNT(DISTINCT performer_id) > 1
        ),
        recordings_with_vocals AS (
            SELECT DISTINCT rp.recording_id
            FROM recording_performers rp
            JOIN instruments i ON rp.instrument_id = i.id
            WHERE i.name = 'Vocals'
            AND rp.recording_id IN (SELECT recording_id FROM multi_performer_recordings)
        )
        SELECT
            mpr.recording_id,
            CASE WHEN rwv.recording_id IS NOT NULL THEN true ELSE false END as has_vocals
        FROM multi_performer_recordings mpr
        LEFT JOIN recordings_with_vocals rwv ON mpr.recording_id = rwv.recording_id
        ORDER BY mpr.recording_id
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    return cur.fetchall()


def get_existing_contributions(cur, bot_user_id: str):
    """Get set of recording IDs that already have contributions from the bot."""
    cur.execute("""
        SELECT recording_id FROM recording_contributions
        WHERE user_id = %s AND is_instrumental IS NOT NULL
    """, (bot_user_id,))
    return {str(row['recording_id']) for row in cur.fetchall()}


def main():
    script = ScriptBase(
        name="populate_vocal_instrumental",
        description="Populate vocal/instrumental data from performer credits",
        epilog="""
Examples:
  python scripts/populate_vocal_instrumental.py --dry-run
  python scripts/populate_vocal_instrumental.py --limit 100
  python scripts/populate_vocal_instrumental.py
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=None)

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    stats = {
        'recordings_processed': 0,
        'vocal_contributions': 0,
        'instrumental_contributions': 0,
        'skipped_existing': 0,
    }

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get or create bot user
            bot_user_id = get_or_create_bot_user(cur, args.dry_run, script.logger)
            if not args.dry_run:
                conn.commit()

            # Get recordings with credits
            script.logger.info("Fetching recordings with performer credits...")
            recordings = get_recordings_with_credits(cur, args.limit)
            script.logger.info(f"Found {len(recordings)} recordings to process")

            # Get existing contributions to skip
            if not args.dry_run:
                existing = get_existing_contributions(cur, bot_user_id)
                script.logger.info(f"Found {len(existing)} existing bot contributions")
            else:
                existing = set()

            # Process recordings in batches
            batch_size = 1000
            batch_values = []

            for row in recordings:
                recording_id = str(row['recording_id'])
                has_vocals = row['has_vocals']

                if recording_id in existing:
                    stats['skipped_existing'] += 1
                    continue

                is_instrumental = not has_vocals  # Vocal = False, Instrumental = True

                if is_instrumental:
                    stats['instrumental_contributions'] += 1
                else:
                    stats['vocal_contributions'] += 1

                stats['recordings_processed'] += 1

                if not args.dry_run:
                    batch_values.append((recording_id, bot_user_id, is_instrumental))

                    # Insert in batches
                    if len(batch_values) >= batch_size:
                        cur.executemany("""
                            INSERT INTO recording_contributions
                                (recording_id, user_id, is_instrumental)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (recording_id, user_id)
                            DO UPDATE SET is_instrumental = EXCLUDED.is_instrumental,
                                          updated_at = CURRENT_TIMESTAMP
                        """, batch_values)
                        conn.commit()
                        script.logger.info(f"  Inserted batch of {len(batch_values)} contributions...")
                        batch_values = []

            # Insert remaining batch
            if batch_values and not args.dry_run:
                cur.executemany("""
                    INSERT INTO recording_contributions
                        (recording_id, user_id, is_instrumental)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (recording_id, user_id)
                    DO UPDATE SET is_instrumental = EXCLUDED.is_instrumental,
                                  updated_at = CURRENT_TIMESTAMP
                """, batch_values)
                conn.commit()
                script.logger.info(f"  Inserted final batch of {len(batch_values)} contributions")

    script.print_summary(stats)
    return True


if __name__ == "__main__":
    run_script(main)
