#!/usr/bin/env python3
"""
Migration: Add tempo_marking column and convert existing BPM data

This migration:
1. Adds tempo_marking column to recording_contributions table
2. Converts existing tempo_bpm values to appropriate tempo markings
3. Updates the performance_key values to include mode (existing keys assumed Major)

Usage:
    # Dry run - see what would be changed
    python scripts/migrate_tempo_markings.py --dry-run

    # Run the migration
    python scripts/migrate_tempo_markings.py
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection

# Tempo marking definitions with BPM ranges
# These are standard jazz tempo terms
TEMPO_MARKINGS = {
    'Ballad': (0, 72),
    'Slow': (72, 108),
    'Medium': (108, 144),
    'Medium-Up': (144, 184),
    'Up-Tempo': (184, 224),
    'Fast': (224, 280),
    'Burning': (280, 999),
}


def bpm_to_marking(bpm: int) -> str:
    """Convert a BPM value to the appropriate tempo marking."""
    for marking, (low, high) in TEMPO_MARKINGS.items():
        if low <= bpm < high:
            return marking
    return 'Fast'  # Fallback for very high tempos


def main():
    script = ScriptBase(
        name="migrate_tempo_markings",
        description="Add tempo_marking column and migrate existing data",
        epilog="""
Examples:
  python scripts/migrate_tempo_markings.py --dry-run
  python scripts/migrate_tempo_markings.py
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if column already exists
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'recording_contributions' AND column_name = 'tempo_marking'
            """)
            column_exists = cur.fetchone() is not None

            if column_exists:
                script.logger.info("Column 'tempo_marking' already exists")
            else:
                script.logger.info("Adding 'tempo_marking' column...")
                if not args.dry_run:
                    cur.execute("""
                        ALTER TABLE recording_contributions
                        ADD COLUMN tempo_marking VARCHAR(20)
                    """)
                    conn.commit()
                    script.logger.info("Column added successfully")
                else:
                    script.logger.info("[DRY RUN] Would add tempo_marking column")

            # Get existing contributions with tempo_bpm
            if column_exists or not args.dry_run:
                cur.execute("""
                    SELECT id, tempo_bpm, tempo_marking
                    FROM recording_contributions
                    WHERE tempo_bpm IS NOT NULL
                """)
            else:
                # In dry-run when column doesn't exist, just get tempo_bpm
                cur.execute("""
                    SELECT id, tempo_bpm
                    FROM recording_contributions
                    WHERE tempo_bpm IS NOT NULL
                """)
            contributions = cur.fetchall()

            script.logger.info(f"Found {len(contributions)} contributions with tempo_bpm values")

            # Convert BPM to marking
            updates = []
            for contrib in contributions:
                contrib_id = contrib['id']
                bpm = contrib['tempo_bpm']
                current_marking = contrib.get('tempo_marking')

                if current_marking:
                    script.logger.debug(f"  Skipping {contrib_id} - already has marking: {current_marking}")
                    continue

                new_marking = bpm_to_marking(bpm)
                updates.append((contrib_id, bpm, new_marking))
                script.logger.info(f"  {bpm} BPM -> {new_marking}")

            if updates:
                script.logger.info(f"Updating {len(updates)} contributions...")
                if not args.dry_run:
                    for contrib_id, bpm, marking in updates:
                        cur.execute("""
                            UPDATE recording_contributions
                            SET tempo_marking = %s
                            WHERE id = %s
                        """, (marking, contrib_id))
                    conn.commit()
                    script.logger.info("Updates complete")
                else:
                    script.logger.info("[DRY RUN] Would update tempo markings")
            else:
                script.logger.info("No updates needed")

    script.print_summary({
        'column_added': not column_exists,
        'contributions_updated': len(updates) if not args.dry_run else f"{len(updates)} (dry run)",
    })

    return True


if __name__ == "__main__":
    run_script(main)
