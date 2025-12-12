#!/usr/bin/env python3
"""
Find recordings where the leader attribution may be incorrect.

This script identifies recordings where:
1. The album title suggests a specific artist (e.g., "The Dave Pell Octet")
2. But that artist is marked as 'sideman' instead of 'leader'
3. And someone else is marked as 'leader'

Usage:
    python find_leader_mismatches.py [--fix] [--dry-run]

Options:
    --fix       Attempt to fix the mismatches by swapping leader/sideman roles
    --dry-run   Show what would be fixed without making changes (implies --fix)
"""

import sys
import os
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import db_utils as db
from mb_performer_importer import normalize_group_name

def find_potential_mismatches():
    """
    Find recordings where the album title contains a performer's name
    but that performer is not marked as leader.
    """

    # Get all recordings with their performers
    query = """
        SELECT
            r.id as recording_id,
            r.album_title,
            r.recording_year,
            s.title as song_title,
            rp.role,
            p.id as performer_id,
            p.name as performer_name
        FROM recordings r
        JOIN songs s ON r.song_id = s.id
        JOIN recording_performers rp ON r.id = rp.recording_id
        JOIN performers p ON rp.performer_id = p.id
        WHERE r.album_title IS NOT NULL
        ORDER BY r.id, rp.role DESC
    """

    results = db.execute_query(query, fetch_all=True)

    # Group by recording
    recordings = {}
    for row in results:
        rec_id = str(row['recording_id'])
        if rec_id not in recordings:
            recordings[rec_id] = {
                'album_title': row['album_title'],
                'recording_year': row['recording_year'],
                'song_title': row['song_title'],
                'performers': []
            }
        recordings[rec_id]['performers'].append({
            'id': row['performer_id'],
            'name': row['performer_name'],
            'role': row['role']
        })

    mismatches = []

    for rec_id, rec in recordings.items():
        album_title = rec['album_title']
        normalized_album = normalize_group_name(album_title)

        # Find current leader(s)
        leaders = [p for p in rec['performers'] if p['role'] == 'leader']
        sidemen = [p for p in rec['performers'] if p['role'] == 'sideman']

        # Check if any sideman's name matches the normalized album title
        for sideman in sidemen:
            sideman_normalized = sideman['name'].lower().strip()

            if sideman_normalized == normalized_album:
                # Found a mismatch - sideman's name matches album but they're not leader
                mismatches.append({
                    'recording_id': rec_id,
                    'album_title': album_title,
                    'normalized_album': normalized_album,
                    'song_title': rec['song_title'],
                    'recording_year': rec['recording_year'],
                    'should_be_leader': sideman,
                    'current_leaders': leaders,
                    'all_performers': rec['performers']
                })

    return mismatches


def fix_mismatch(mismatch, dry_run=True):
    """
    Fix a single mismatch by:
    1. Setting the correct performer as leader
    2. Demoting the incorrect leader to sideman (if they're a performer, not other)
    """
    recording_id = mismatch['recording_id']
    correct_leader_id = mismatch['should_be_leader']['id']

    if dry_run:
        print(f"  [DRY RUN] Would set {mismatch['should_be_leader']['name']} as leader")
        for leader in mismatch['current_leaders']:
            print(f"  [DRY RUN] Would demote {leader['name']} to sideman")
        return True

    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Set correct performer as leader
                cur.execute("""
                    UPDATE recording_performers
                    SET role = 'leader'
                    WHERE recording_id = %s AND performer_id = %s
                """, (recording_id, correct_leader_id))

                # Demote current leaders to sideman
                for leader in mismatch['current_leaders']:
                    cur.execute("""
                        UPDATE recording_performers
                        SET role = 'sideman'
                        WHERE recording_id = %s AND performer_id = %s AND role = 'leader'
                    """, (recording_id, leader['id']))

            conn.commit()

        return True
    except Exception as e:
        print(f"  ERROR fixing: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Find recordings with incorrect leader attribution')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix mismatches')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')
    args = parser.parse_args()

    print("Searching for potential leader mismatches...")
    print()

    mismatches = find_potential_mismatches()

    if not mismatches:
        print("No mismatches found!")
        return

    print(f"Found {len(mismatches)} potential mismatches:")
    print("=" * 80)

    for i, m in enumerate(mismatches, 1):
        print(f"\n{i}. {m['song_title']} ({m['recording_year'] or 'Unknown year'})")
        print(f"   Album: {m['album_title']}")
        print(f"   Normalized: '{m['normalized_album']}'")
        print(f"   Should be leader: {m['should_be_leader']['name']} (currently {m['should_be_leader']['role']})")
        print(f"   Current leader(s): {', '.join(l['name'] for l in m['current_leaders']) or 'None'}")

        if args.fix or args.dry_run:
            fix_mismatch(m, dry_run=args.dry_run)

    print()
    print("=" * 80)
    print(f"Total: {len(mismatches)} potential mismatches")

    if not args.fix and not args.dry_run:
        print()
        print("Run with --dry-run to see what would be fixed")
        print("Run with --fix to apply fixes")


if __name__ == '__main__':
    main()
