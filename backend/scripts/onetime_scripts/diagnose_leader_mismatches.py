#!/usr/bin/env python3
"""
Diagnose Leader Mismatches

Scans cached MusicBrainz recording files and compares the expected leader
(derived from artist-credit) against the actual leader in the database.

This helps identify recordings where the wrong performer was marked as leader
due to the "&" vs "and" normalization bug.

Usage:
    python diagnose_leader_mismatches.py [--fix] [--limit N]

Options:
    --fix       Actually fix the mismatches in the database
    --limit N   Only process first N cached files (for testing)
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_performer_importer import normalize_group_name, is_performer_leader_of_group
from cache_utils import get_cache_dir

def get_expected_leader_name(recording_data):
    """
    Extract the expected leader name from recording's artist-credit.
    Returns the normalized name that should be the leader.
    """
    artist_credits = recording_data.get('artist-credit') or []

    for credit in artist_credits:
        if isinstance(credit, dict) and 'artist' in credit:
            artist = credit['artist']
            artist_name = artist.get('name', '')
            artist_type = artist.get('type', '')

            # If it's a group, normalize to get the leader's name
            if artist_type == 'Group' or any(x in artist_name.lower() for x in
                ['orchestra', 'band', 'trio', 'quartet', 'quintet', 'sextet', 'septet', 'octet', 'ensemble']):
                normalized = normalize_group_name(artist_name)
                if normalized and normalized != artist_name.lower():
                    return normalized
            else:
                # Individual artist - they're the leader
                return artist_name.lower()

    return None

def find_mismatches(limit=None, verbose=True):
    """
    Scan cached recordings and find leader mismatches.

    Returns list of dicts with mismatch info.
    """
    cache_dir = get_cache_dir('musicbrainz') / 'recordings'

    if not cache_dir.exists():
        print(f"Cache directory not found: {cache_dir}")
        return []

    mismatches = []
    processed = 0

    # Get all cached recording files
    cache_files = list(cache_dir.glob('recording_*.json'))
    print(f"Found {len(cache_files)} cached recording files")

    if limit:
        cache_files = cache_files[:limit]
        print(f"Processing first {limit} files")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for cache_file in cache_files:
                processed += 1

                if processed % 500 == 0:
                    print(f"  Processed {processed} files...")

                try:
                    with open(cache_file) as f:
                        cache_data = json.load(f)

                    recording_data = cache_data.get('data', {})
                    mb_recording_id = cache_file.stem.replace('recording_', '')

                    # Get expected leader from artist-credit
                    expected_leader = get_expected_leader_name(recording_data)
                    if not expected_leader:
                        continue

                    # Get actual leader from database
                    cur.execute("""
                        SELECT r.id, r.album_title, r.musicbrainz_id,
                               p.name as leader_name, p.id as leader_id
                        FROM recordings r
                        JOIN recording_performers rp ON r.id = rp.recording_id
                        JOIN performers p ON rp.performer_id = p.id
                        WHERE r.musicbrainz_id = %s
                          AND rp.role = 'leader'
                        LIMIT 1
                    """, (mb_recording_id,))

                    row = cur.fetchone()
                    if not row:
                        continue

                    actual_leader = row['leader_name'].lower()

                    # Check if they match
                    if expected_leader != actual_leader:
                        # Check if actual leader is in the group name pattern
                        artist_credits = recording_data.get('artist-credit') or []
                        group_name = ''
                        for credit in artist_credits:
                            if isinstance(credit, dict) and 'artist' in credit:
                                group_name = credit['artist'].get('name', '')
                                break

                        # Only flag if actual leader doesn't match expected
                        # and expected leader is actually a performer on the recording
                        relations = recording_data.get('relations') or []
                        performer_names = set()
                        for rel in relations:
                            if rel.get('target-type') == 'artist' and 'artist' in rel:
                                performer_names.add(rel['artist'].get('name', '').lower())

                        if expected_leader in performer_names:
                            mismatch = {
                                'recording_id': row['id'],
                                'mb_recording_id': mb_recording_id,
                                'album_title': row['album_title'],
                                'group_name': group_name,
                                'expected_leader': expected_leader,
                                'actual_leader': actual_leader,
                                'actual_leader_id': row['leader_id'],
                            }

                            # Find the expected leader's performer ID
                            cur.execute("""
                                SELECT p.id, p.name
                                FROM performers p
                                JOIN recording_performers rp ON p.id = rp.performer_id
                                WHERE rp.recording_id = %s
                                  AND LOWER(p.name) = %s
                            """, (row['id'], expected_leader))

                            expected_row = cur.fetchone()
                            if expected_row:
                                mismatch['expected_leader_id'] = expected_row['id']
                                mismatch['expected_leader_name'] = expected_row['name']
                                mismatches.append(mismatch)

                                if verbose:
                                    print(f"\nMismatch found:")
                                    print(f"  Album: {row['album_title']}")
                                    print(f"  Group: {group_name}")
                                    print(f"  Expected leader: {expected_leader}")
                                    print(f"  Actual leader: {actual_leader}")

                except Exception as e:
                    if verbose:
                        print(f"Error processing {cache_file}: {e}")
                    continue

    return mismatches

def fix_mismatches(mismatches):
    """
    Fix the leader mismatches in the database.
    """
    if not mismatches:
        print("No mismatches to fix")
        return

    print(f"\nFixing {len(mismatches)} mismatches...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for mismatch in mismatches:
                recording_id = mismatch['recording_id']
                expected_leader_id = mismatch.get('expected_leader_id')

                if not expected_leader_id:
                    print(f"  Skipping {mismatch['album_title']} - no expected leader ID")
                    continue

                # Demote current leader to sideman
                cur.execute("""
                    UPDATE recording_performers
                    SET role = 'sideman'
                    WHERE recording_id = %s AND role = 'leader'
                """, (recording_id,))

                # Promote expected leader
                cur.execute("""
                    UPDATE recording_performers
                    SET role = 'leader'
                    WHERE recording_id = %s AND performer_id = %s
                """, (recording_id, expected_leader_id))

                print(f"  Fixed: {mismatch['album_title']} - {mismatch['actual_leader']} -> {mismatch['expected_leader_name']}")

            conn.commit()

    print(f"\nFixed {len(mismatches)} recordings")

def main():
    parser = argparse.ArgumentParser(description='Diagnose leader mismatches in recordings')
    parser.add_argument('--fix', action='store_true', help='Actually fix the mismatches')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--quiet', action='store_true', help='Suppress individual mismatch output')
    args = parser.parse_args()

    print("Scanning for leader mismatches...")
    print("=" * 60)

    mismatches = find_mismatches(limit=args.limit, verbose=not args.quiet)

    print("=" * 60)
    print(f"\nFound {len(mismatches)} potential leader mismatches")

    if mismatches and not args.fix:
        print("\nRun with --fix to correct these mismatches")
        print("\nSummary of mismatches:")
        for m in mismatches[:20]:  # Show first 20
            print(f"  {m['album_title'][:40]}: {m['actual_leader']} -> {m['expected_leader']}")
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")

    if args.fix:
        fix_mismatches(mismatches)

if __name__ == '__main__':
    main()
