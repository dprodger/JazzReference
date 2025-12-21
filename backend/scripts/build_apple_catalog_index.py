#!/usr/bin/env python3
"""
Build Indexed Apple Music Catalog Database

Loads the downloaded Apple Music parquet files into an indexed DuckDB database
for fast searching. This is a one-time operation that makes subsequent searches
nearly instant.

IMPORTANT: The Apple Music Feed has a known issue where primaryArtists[].name
contains localized names (e.g., Japanese) instead of English. To get English
artist names, you must also download the 'artists' catalog, which contains
the nameDefault field with English names.

Usage:
  python build_apple_catalog_index.py

  # Rebuild from scratch (delete existing database)
  python build_apple_catalog_index.py --rebuild

  # Show statistics about the indexed database
  python build_apple_catalog_index.py --stats
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from script_base import ScriptBase, run_script

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


# Default paths
DEFAULT_CATALOG_DIR = Path(__file__).parent.parent / "data" / "apple_music_catalog"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "apple_music_catalog.duckdb"


def get_latest_export_dir(catalog_dir: Path, feed_name: str) -> Path:
    """Get the most recent export directory for a feed."""
    feed_dir = catalog_dir / feed_name
    if not feed_dir.exists():
        return None

    export_dirs = sorted(
        [d for d in feed_dir.iterdir() if d.is_dir()],
        reverse=True
    )
    return export_dirs[0] if export_dirs else None


def main() -> bool:
    script = ScriptBase(
        name="build_apple_catalog_index",
        description="Build indexed DuckDB database from Apple Music parquet files",
        epilog="""
This script loads the downloaded Apple Music catalog (parquet files) into
an indexed DuckDB database for fast searching.

The indexed database will be ~2-3GB and makes searches nearly instant
compared to scanning 150+ parquet files for each query.

Examples:
  # Build the indexed database (first time)
  python build_apple_catalog_index.py

  # Rebuild from scratch
  python build_apple_catalog_index.py --rebuild

  # Check database statistics
  python build_apple_catalog_index.py --stats
        """
    )

    script.parser.add_argument(
        '--rebuild',
        action='store_true',
        help='Delete existing database and rebuild from scratch'
    )

    script.parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics about the indexed database'
    )

    script.parser.add_argument(
        '--albums-only',
        action='store_true',
        help='Only index albums (skip songs to save disk space)'
    )

    script.parser.add_argument(
        '--skip-song-indexes',
        action='store_true',
        help='Load songs but skip creating indexes (faster, less memory)'
    )

    script.parser.add_argument(
        '--catalog-dir',
        type=Path,
        default=DEFAULT_CATALOG_DIR,
        help=f'Directory containing parquet files (default: {DEFAULT_CATALOG_DIR})'
    )

    script.parser.add_argument(
        '--db-path',
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f'Output database path (default: {DEFAULT_DB_PATH})'
    )

    script.add_debug_arg()
    args = script.parse_args()

    if not DUCKDB_AVAILABLE:
        script.logger.error("duckdb is required. Install with: pip install duckdb")
        return False

    db_path = args.db_path
    catalog_dir = args.catalog_dir

    # Stats mode
    if args.stats:
        if not db_path.exists():
            script.logger.error(f"Database not found: {db_path}")
            script.logger.info("Run without --stats to build the database first.")
            return False

        conn = duckdb.connect(str(db_path), read_only=True)

        script.logger.info("Apple Music Catalog Index Statistics")
        script.logger.info("=" * 50)

        # Get table counts
        for table in ['albums', 'songs']:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                script.logger.info(f"  {table}: {count:,} records")
            except Exception as e:
                script.logger.info(f"  {table}: not found")

        # Get database file size
        db_size = db_path.stat().st_size / (1024 * 1024 * 1024)
        script.logger.info(f"  Database size: {db_size:.2f} GB")

        # Test search performance
        script.logger.info("\nSearch Performance Test:")
        start = time.time()
        result = conn.execute("""
            SELECT id, name, artist_name
            FROM albums
            WHERE LOWER(name) LIKE '%kind of blue%'
            AND LOWER(artist_name) LIKE '%miles davis%'
            LIMIT 5
        """).fetchall()
        elapsed = (time.time() - start) * 1000
        script.logger.info(f"  'Kind of Blue' search: {elapsed:.1f}ms ({len(result)} results)")

        conn.close()
        return True

    # Build mode
    if db_path.exists():
        if args.rebuild:
            script.logger.info(f"Removing existing database: {db_path}")
            db_path.unlink()
        else:
            script.logger.info(f"Database already exists: {db_path}")
            script.logger.info("Use --rebuild to recreate, or --stats to view statistics.")
            return True

    # Find parquet files
    albums_dir = get_latest_export_dir(catalog_dir, 'albums')
    songs_dir = get_latest_export_dir(catalog_dir, 'songs')
    artists_dir = get_latest_export_dir(catalog_dir, 'artists')

    if not albums_dir:
        script.logger.error(f"No albums data found in {catalog_dir}/albums/")
        script.logger.info("Run download_apple_catalog.py --feed albums first.")
        return False

    albums_glob = str(albums_dir / '*.parquet')
    songs_glob = str(songs_dir / '*.parquet') if songs_dir else None
    artists_glob = str(artists_dir / '*.parquet') if artists_dir else None

    script.logger.info("Building indexed Apple Music catalog database...")
    script.logger.info(f"  Albums source: {albums_dir}")
    if songs_dir:
        script.logger.info(f"  Songs source: {songs_dir}")
    if artists_dir:
        script.logger.info(f"  Artists source: {artists_dir}")
    else:
        script.logger.warning("  Artists catalog not found - will use localized artist names!")
        script.logger.warning("  Run: python download_apple_catalog.py --feed artists")
        script.logger.warning("  Then rebuild with --rebuild to get English artist names.")
    script.logger.info(f"  Output: {db_path}")
    script.logger.info("")

    # Create database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    # Load artists lookup table first (if available) for English names
    has_artists = False
    if artists_glob:
        script.logger.info("Loading artists (for English name lookup)...")
        start = time.time()

        conn.execute(f"""
            CREATE TABLE artists AS
            SELECT
                id,
                nameDefault as name_english,
                name['default'] as name_default,
                CAST(name AS VARCHAR) as name_localized_json
            FROM read_parquet('{artists_glob}')
            WHERE nameDefault IS NOT NULL
        """)

        artist_count = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
        elapsed = time.time() - start
        script.logger.info(f"  Loaded {artist_count:,} artists in {elapsed:.1f}s")

        # Create artist index for fast lookups
        conn.execute("CREATE INDEX idx_artist_id ON artists(id)")
        has_artists = True

    # Load albums - join with artists if available to get English names
    script.logger.info("Loading albums...")
    start = time.time()

    if has_artists:
        # Join with artists table to get English artist names
        conn.execute(f"""
            CREATE TABLE albums AS
            SELECT
                a.id,
                a.nameDefault as name,
                COALESCE(art.name_english, a.primaryArtists[1].name) as artist_name,
                a.primaryArtists[1].id as artist_id,
                CAST(a.releaseDate AS VARCHAR) as release_date,
                len(a.songs) as track_count,
                a.upc,
                a.urlTemplate as url_template,
                -- Store full primaryArtists for multi-artist albums
                CAST(a.primaryArtists AS VARCHAR) as primary_artists_json
            FROM read_parquet('{albums_glob}') a
            LEFT JOIN artists art ON a.primaryArtists[1].id = art.id
            WHERE a.nameDefault IS NOT NULL
        """)
    else:
        # No artists table - use localized names (fallback)
        conn.execute(f"""
            CREATE TABLE albums AS
            SELECT
                id,
                nameDefault as name,
                primaryArtists[1].name as artist_name,
                primaryArtists[1].id as artist_id,
                CAST(releaseDate AS VARCHAR) as release_date,
                len(songs) as track_count,
                upc,
                urlTemplate as url_template,
                -- Store full primaryArtists for multi-artist albums
                CAST(primaryArtists AS VARCHAR) as primary_artists_json
            FROM read_parquet('{albums_glob}')
            WHERE nameDefault IS NOT NULL
        """)

    album_count = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
    elapsed = time.time() - start
    script.logger.info(f"  Loaded {album_count:,} albums in {elapsed:.1f}s")

    # Verify we got English names
    if has_artists:
        sample = conn.execute("""
            SELECT artist_name FROM albums
            WHERE artist_id = '120922'
            LIMIT 1
        """).fetchone()
        if sample:
            script.logger.info(f"  Sample artist name (ID 120922): {sample[0]}")

    # Create album indexes
    script.logger.info("Creating album indexes...")
    start = time.time()

    conn.execute("CREATE INDEX idx_album_name ON albums(LOWER(name))")
    conn.execute("CREATE INDEX idx_album_artist ON albums(LOWER(artist_name))")
    conn.execute("CREATE INDEX idx_album_id ON albums(id)")

    elapsed = time.time() - start
    script.logger.info(f"  Created indexes in {elapsed:.1f}s")

    # Load songs if available and not --albums-only
    if songs_glob and not args.albums_only:
        script.logger.info("Loading songs...")
        start = time.time()

        if has_artists:
            # Join with artists table to get English artist names
            conn.execute(f"""
                CREATE TABLE songs AS
                SELECT
                    s.id,
                    s.nameDefault as name,
                    COALESCE(art.name_english, s.primaryArtists[1].name) as artist_name,
                    s.primaryArtists[1].id as artist_id,
                    s.album.id as album_id,
                    s.album.name as album_name,
                    s.volumeNumber as disc_number,
                    s.trackNumber as track_number,
                    s.durationInMillis as duration_ms,
                    s.isrc,
                    s.shortPreview as preview_url
                FROM read_parquet('{songs_glob}') s
                LEFT JOIN artists art ON s.primaryArtists[1].id = art.id
                WHERE s.nameDefault IS NOT NULL
            """)
        else:
            # No artists table - use localized names (fallback)
            conn.execute(f"""
                CREATE TABLE songs AS
                SELECT
                    id,
                    nameDefault as name,
                    primaryArtists[1].name as artist_name,
                    primaryArtists[1].id as artist_id,
                    album.id as album_id,
                    album.name as album_name,
                    volumeNumber as disc_number,
                    trackNumber as track_number,
                    durationInMillis as duration_ms,
                    isrc,
                    shortPreview as preview_url
                FROM read_parquet('{songs_glob}')
                WHERE nameDefault IS NOT NULL
            """)

        song_count = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        elapsed = time.time() - start
        script.logger.info(f"  Loaded {song_count:,} songs in {elapsed:.1f}s")

        # Create song indexes (unless --skip-song-indexes)
        if args.skip_song_indexes:
            script.logger.info("Skipping song indexes (--skip-song-indexes)")
        else:
            script.logger.info("Creating song indexes...")
            start = time.time()

            conn.execute("CREATE INDEX idx_song_name ON songs(LOWER(name))")
            conn.execute("CREATE INDEX idx_song_artist ON songs(LOWER(artist_name))")
            conn.execute("CREATE INDEX idx_song_album ON songs(album_id)")
            conn.execute("CREATE INDEX idx_song_id ON songs(id)")

            elapsed = time.time() - start
            script.logger.info(f"  Created indexes in {elapsed:.1f}s")
    elif args.albums_only:
        script.logger.info("Skipping songs (--albums-only mode)")

    # Drop the artists lookup table to save space (data is now in albums/songs)
    if has_artists:
        script.logger.info("Dropping artists lookup table (no longer needed)...")
        conn.execute("DROP TABLE artists")

    conn.close()

    # Final stats
    db_size = db_path.stat().st_size / (1024 * 1024 * 1024)
    script.logger.info("")
    script.logger.info(f"✓ Database created: {db_path}")
    script.logger.info(f"  Size: {db_size:.2f} GB")
    if has_artists:
        script.logger.info(f"  Artist names: English (from artists catalog)")
    else:
        script.logger.info(f"  Artist names: Localized (artists catalog not available)")
    script.logger.info("")
    script.logger.info("Run with --stats to test search performance.")
    script.logger.info("")
    script.logger.info("To upload to MotherDuck:")
    script.logger.info(f"  duckdb")
    script.logger.info(f"  ATTACH 'md:'")
    script.logger.info(f"  CREATE OR REPLACE DATABASE apple_music_feed FROM '{db_path}'")

    return True


if __name__ == "__main__":
    run_script(main)
