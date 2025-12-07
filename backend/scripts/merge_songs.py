#!/usr/bin/env python3
"""
Merge Songs Script

Merges two songs that represent the same work but have different MusicBrainz IDs.
The "extra" song's recordings are moved to the "master" song, and the extra song
is deleted. The master song's second_mb_id is set to the extra song's musicbrainz_id.

Usage:
    python scripts/merge_songs.py <song_id_1> <song_id_2> [--dry-run]

Example:
    python scripts/merge_songs.py 123e4567-e89b-12d3-a456-426614174000 987fcdeb-51a2-3bc4-d567-890123456789
    python scripts/merge_songs.py 123e4567-e89b-12d3-a456-426614174000 987fcdeb-51a2-3bc4-d567-890123456789 --dry-run
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection


def get_song_info(conn, song_id: str) -> dict | None:
    """Fetch song info including recording count."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                s.id,
                s.title,
                s.composer,
                s.musicbrainz_id,
                s.second_mb_id,
                s.wikipedia_url,
                COUNT(r.id) as recording_count
            FROM songs s
            LEFT JOIN recordings r ON r.song_id = s.id
            WHERE s.id = %s
            GROUP BY s.id
        """, (song_id,))
        result = cur.fetchone()
        return dict(result) if result else None


def get_repertoire_count(conn, song_id: str) -> int:
    """Get count of repertoire references to this song."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as count
            FROM repertoire_songs
            WHERE song_id = %s
        """, (song_id,))
        return cur.fetchone()['count']


def get_duplicate_recording_ids(conn, master_id: str, extra_id: str) -> set:
    """Find MB recording IDs that exist in both songs."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT r1.musicbrainz_id
            FROM recordings r1
            INNER JOIN recordings r2 ON r1.musicbrainz_id = r2.musicbrainz_id
            WHERE r1.song_id = %s
              AND r2.song_id = %s
              AND r1.musicbrainz_id IS NOT NULL
        """, (master_id, extra_id))
        return {row['musicbrainz_id'] for row in cur.fetchall()}


def display_song_info(song: dict, repertoire_count: int, label: str):
    """Display formatted song information."""
    print(f"\n{label}:")
    print(f"  ID:              {song['id']}")
    print(f"  Title:           {song['title']}")
    print(f"  Composer:        {song['composer'] or '(none)'}")
    print(f"  MusicBrainz ID:  {song['musicbrainz_id'] or '(none)'}")
    print(f"  Second MB ID:    {song['second_mb_id'] or '(none)'}")
    print(f"  Wikipedia:       {song['wikipedia_url'] or '(none)'}")
    print(f"  Recordings:      {song['recording_count']}")
    print(f"  In repertoires:  {repertoire_count}")


def merge_songs(master_id: str, extra_id: str, extra_mb_id: str, dry_run: bool = False):
    """
    Merge extra song into master song.

    Args:
        master_id: UUID of the song to keep
        extra_id: UUID of the song to merge and delete
        extra_mb_id: MusicBrainz work ID of the extra song (to set as second_mb_id)
        dry_run: If True, don't make any changes
    """
    prefix = "[DRY RUN] " if dry_run else ""

    with get_db_connection() as conn:
        # Find duplicate recordings (same MB recording ID in both songs)
        duplicates = get_duplicate_recording_ids(conn, master_id, extra_id)

        if duplicates:
            print(f"\n{prefix}Found {len(duplicates)} duplicate recording(s) (same MB recording ID):")
            for mb_id in duplicates:
                print(f"  - {mb_id}")
            print(f"{prefix}These will be skipped (master's copy kept, extra's copy deleted)")

        with conn.cursor() as cur:
            # Step 1: Set second_mb_id on master song
            print(f"\n{prefix}Setting second_mb_id on master song to: {extra_mb_id}")
            if not dry_run:
                cur.execute("""
                    UPDATE songs
                    SET second_mb_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (extra_mb_id, master_id))

            # Step 2: Delete duplicate recordings from extra song
            if duplicates:
                print(f"{prefix}Deleting {len(duplicates)} duplicate recording(s) from extra song...")
                if not dry_run:
                    cur.execute("""
                        DELETE FROM recordings
                        WHERE song_id = %s
                          AND musicbrainz_id = ANY(%s)
                    """, (extra_id, list(duplicates)))
                    print(f"  Deleted {cur.rowcount} duplicate recording(s)")

            # Step 3: Move remaining recordings from extra to master
            # Also set source_mb_work_id to track where they came from
            print(f"{prefix}Moving recordings from extra song to master...")
            if not dry_run:
                cur.execute("""
                    UPDATE recordings
                    SET song_id = %s,
                        source_mb_work_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE song_id = %s
                """, (master_id, extra_mb_id, extra_id))
                print(f"  Moved {cur.rowcount} recording(s)")
            else:
                # Count how many would be moved
                cur.execute("""
                    SELECT COUNT(*) as count FROM recordings WHERE song_id = %s
                """, (extra_id,))
                count = cur.fetchone()['count']
                print(f"  Would move {count} recording(s)")

            # Step 4: Move repertoire references from extra to master
            print(f"{prefix}Moving repertoire references from extra song to master...")
            if not dry_run:
                # Use ON CONFLICT to handle case where user already has master in repertoire
                cur.execute("""
                    UPDATE repertoire_songs
                    SET song_id = %s
                    WHERE song_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM repertoire_songs rs2
                          WHERE rs2.repertoire_id = repertoire_songs.repertoire_id
                            AND rs2.song_id = %s
                      )
                """, (master_id, extra_id, master_id))
                moved_count = cur.rowcount

                # Delete any remaining (duplicates where user had both songs)
                cur.execute("""
                    DELETE FROM repertoire_songs
                    WHERE song_id = %s
                """, (extra_id,))
                deleted_count = cur.rowcount

                print(f"  Moved {moved_count} repertoire reference(s)")
                if deleted_count > 0:
                    print(f"  Removed {deleted_count} duplicate repertoire reference(s) (user had both songs)")
            else:
                cur.execute("""
                    SELECT COUNT(*) as count FROM repertoire_songs WHERE song_id = %s
                """, (extra_id,))
                count = cur.fetchone()['count']
                print(f"  Would move {count} repertoire reference(s)")

            # Step 5: Delete the extra song
            print(f"{prefix}Deleting extra song...")
            if not dry_run:
                cur.execute("""
                    DELETE FROM songs WHERE id = %s
                """, (extra_id,))
                print(f"  Deleted song: {extra_id}")
            else:
                print(f"  Would delete song: {extra_id}")

        if not dry_run:
            conn.commit()
            print(f"\nMerge complete!")
        else:
            print(f"\n[DRY RUN] No changes made. Run without --dry-run to execute.")


def main():
    parser = argparse.ArgumentParser(
        description='Merge two songs that represent the same work with different MusicBrainz IDs.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('song_id_1', help='First song UUID')
    parser.add_argument('song_id_2', help='Second song UUID')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without executing them')

    args = parser.parse_args()

    # Validate UUIDs look reasonable
    for song_id in [args.song_id_1, args.song_id_2]:
        if len(song_id) != 36 or song_id.count('-') != 4:
            print(f"Error: '{song_id}' doesn't look like a valid UUID")
            sys.exit(1)

    if args.song_id_1 == args.song_id_2:
        print("Error: Both song IDs are the same")
        sys.exit(1)

    # Fetch song information
    with get_db_connection() as conn:
        song1 = get_song_info(conn, args.song_id_1)
        song2 = get_song_info(conn, args.song_id_2)

        if not song1:
            print(f"Error: Song not found: {args.song_id_1}")
            sys.exit(1)

        if not song2:
            print(f"Error: Song not found: {args.song_id_2}")
            sys.exit(1)

        rep_count1 = get_repertoire_count(conn, args.song_id_1)
        rep_count2 = get_repertoire_count(conn, args.song_id_2)

    # Display both songs
    print("=" * 60)
    print("MERGE SONGS")
    print("=" * 60)

    display_song_info(song1, rep_count1, "Song 1")
    display_song_info(song2, rep_count2, "Song 2")

    # Check for potential issues
    warnings = []

    if song1['title'].lower() != song2['title'].lower():
        warnings.append(f"Titles don't match: '{song1['title']}' vs '{song2['title']}'")

    if song1['second_mb_id']:
        warnings.append(f"Song 1 already has a second_mb_id: {song1['second_mb_id']}")

    if song2['second_mb_id']:
        warnings.append(f"Song 2 already has a second_mb_id: {song2['second_mb_id']}")

    if not song1['musicbrainz_id']:
        warnings.append("Song 1 has no MusicBrainz ID")

    if not song2['musicbrainz_id']:
        warnings.append("Song 2 has no MusicBrainz ID")

    if warnings:
        print("\n" + "!" * 60)
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print("!" * 60)

    # Ask user which should be master
    print("\n" + "-" * 60)
    print("Which song should be the MASTER (the one that remains)?")
    print("  1) Song 1")
    print("  2) Song 2")
    print("  q) Quit without merging")
    print("-" * 60)

    while True:
        choice = input("\nEnter choice [1/2/q]: ").strip().lower()

        if choice == 'q':
            print("Aborted.")
            sys.exit(0)
        elif choice == '1':
            master = song1
            extra = song2
            break
        elif choice == '2':
            master = song2
            extra = song1
            break
        else:
            print("Invalid choice. Please enter 1, 2, or q.")

    # Confirm the merge
    print(f"\n" + "=" * 60)
    print("MERGE PLAN:")
    print(f"  Master (keep):  {master['title']} ({master['recording_count']} recordings)")
    print(f"  Extra (delete): {extra['title']} ({extra['recording_count']} recordings)")
    print(f"  ")
    print(f"  Master's musicbrainz_id:  {master['musicbrainz_id']}")
    print(f"  Master's second_mb_id:    {extra['musicbrainz_id']} (will be set)")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    confirm = input("\nProceed with merge? [y/N]: ").strip().lower()

    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)

    # Execute the merge
    merge_songs(
        master_id=str(master['id']),
        extra_id=str(extra['id']),
        extra_mb_id=extra['musicbrainz_id'],
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
