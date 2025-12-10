#!/usr/bin/env python3
"""
One-time script to clear Spotify search cache for releases with live suffixes.

This enables the new strip_live_suffix fallback search to work for existing releases.

Usage:
    python scripts/clear_live_suffix_cache.py          # Dry run - show what would be deleted
    python scripts/clear_live_suffix_cache.py --delete # Actually delete the files
"""

import os
import sys
import hashlib
import re
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DB_USE_POOLING'] = 'true'
from db_utils import get_db_connection
from spotify_matching import strip_live_suffix


def get_cache_filename(song_title, album_title, artist_name, year=None):
    """Replicate the cache key generation from spotify_client.py"""
    query_parts = [song_title or '']
    if album_title:
        query_parts.append(album_title)
    if artist_name:
        query_parts.append(artist_name)
    if year:
        query_parts.append(str(year))

    query_string = '||'.join(query_parts)
    query_hash = hashlib.md5(query_string.encode()).hexdigest()

    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', song_title.lower())[:50]
    filename = f"search_{safe_title}_{query_hash}.json"
    return filename


def main():
    parser = argparse.ArgumentParser(description='Clear Spotify cache for releases with live suffixes')
    parser.add_argument('--delete', action='store_true', help='Actually delete the files (default is dry run)')
    args = parser.parse_args()

    # Determine cache directory
    cache_dir = Path(__file__).parent.parent.parent / 'cache' / 'spotify' / 'searches'
    if not cache_dir.exists():
        print(f'Cache directory not found: {cache_dir}')
        return

    print(f'Cache directory: {cache_dir}')
    print()

    # Get releases with strippable suffixes
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT r.title, r.artist_credit
                FROM releases r
                WHERE r.title IS NOT NULL
                ORDER BY r.title
            ''')
            releases = cur.fetchall()

    affected = []
    for row in releases:
        title = row['title']
        artist = row['artist_credit']
        stripped = strip_live_suffix(title)
        if stripped != title:
            affected.append((title, artist))

    print(f'Found {len(affected)} releases with live suffixes')
    print()

    # Find cache files to delete
    files_to_delete = []
    for title, artist in affected:
        # Album search cache uses 'album' as the first part
        filename = get_cache_filename('album', title, artist)
        cache_path = cache_dir / filename
        if cache_path.exists():
            files_to_delete.append((cache_path, title, artist))

    if not files_to_delete:
        print('No cache files found to delete.')
        print('(These releases may not have been searched yet)')
        return

    print(f'Found {len(files_to_delete)} cache files:')
    print()
    for cache_path, title, artist in files_to_delete:
        print(f'  {cache_path.name}')
        print(f'    "{title}" by {artist}')
        print()

    if args.delete:
        for cache_path, title, artist in files_to_delete:
            cache_path.unlink()
            print(f'Deleted: {cache_path.name}')
        print()
        print(f'Deleted {len(files_to_delete)} cache files')
        print('Run your Spotify matching again to re-search these releases.')
    else:
        print('Dry run - no files deleted.')
        print('Run with --delete to actually delete the files.')


if __name__ == '__main__':
    main()
