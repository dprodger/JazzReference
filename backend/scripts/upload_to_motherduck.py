#!/usr/bin/env python3
"""
Upload local DuckDB database to MotherDuck in batches.

Handles large tables by copying in chunks to avoid timeout issues.

Usage:
    python scripts/upload_to_motherduck.py [--batch-size 1000000] [--table albums|songs]
"""

import argparse
import duckdb
import sys
import time

LOCAL_DB_PATH = 'data/apple_music_catalog.duckdb'
MOTHERDUCK_DB = 'md:apple_music_feed'

def get_table_schema(conn, table_name):
    """Get CREATE TABLE statement for a table."""
    result = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()
    if result:
        return result[0]
    # Fallback: generate from DESCRIBE
    cols = conn.execute(f"DESCRIBE {table_name}").fetchall()
    col_defs = [f'"{col[0]}" {col[1]}' for col in cols]
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(col_defs) + "\n)"

def get_row_count(conn, table_name):
    """Get total row count for a table."""
    return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

MAX_RETRIES = 5
RETRY_DELAY = 15  # seconds


def upload_table(table_name, batch_size=1_000_000, resume_offset=0):
    """Upload a single table to MotherDuck in batches."""

    print(f"\n{'='*60}")
    print(f"Uploading table: {table_name}")
    print(f"{'='*60}")

    # Connect to local database
    local_conn = duckdb.connect(LOCAL_DB_PATH, read_only=True)
    total_rows = get_row_count(local_conn, table_name)
    print(f"Total rows: {total_rows:,}")

    # Get schema
    schema = local_conn.execute(f"DESCRIBE {table_name}").fetchall()
    col_names = [col[0] for col in schema]
    col_types = [col[1] for col in schema]

    # Create column definitions for CREATE TABLE
    col_defs = [f'"{name}" {dtype}' for name, dtype in zip(col_names, col_types)]
    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(col_defs) + "\n)"

    local_conn.close()

    # Connect to MotherDuck
    print(f"Connecting to MotherDuck...")
    md_conn = duckdb.connect(MOTHERDUCK_DB)

    # Create table if needed
    print(f"Creating table schema...")
    md_conn.execute(create_sql)

    # Check how many rows already exist (for resume)
    existing_rows = get_row_count(md_conn, table_name)
    if existing_rows > 0 and resume_offset == 0:
        print(f"Table already has {existing_rows:,} rows.")
        response = input("Continue from where we left off? (y/n): ")
        if response.lower() == 'y':
            resume_offset = existing_rows
        else:
            response = input("Truncate and start fresh? (y/n): ")
            if response.lower() == 'y':
                md_conn.execute(f"DELETE FROM {table_name}")
                print("Table truncated.")
            else:
                print("Aborting.")
                return

    md_conn.close()

    # Upload in batches
    offset = resume_offset
    batch_num = offset // batch_size + 1
    total_batches = (total_rows - offset + batch_size - 1) // batch_size

    print(f"\nStarting upload from row {offset:,}")
    print(f"Batch size: {batch_size:,}")
    print(f"Batches remaining: {total_batches}")

    while offset < total_rows:
        batch_start = time.time()

        # Reconnect for each batch to avoid long-lived connection timeouts
        local_conn = duckdb.connect(LOCAL_DB_PATH, read_only=True)
        md_conn = duckdb.connect(MOTHERDUCK_DB)

        # Attach local DB to MotherDuck connection (detach first if exists)
        try:
            md_conn.execute("DETACH local_db")
        except:
            pass  # Not attached yet, that's fine
        md_conn.execute(f"ATTACH '{LOCAL_DB_PATH}' AS local_db (READ_ONLY)")

        # Copy batch
        rows_to_copy = min(batch_size, total_rows - offset)
        print(f"\nBatch {batch_num}/{batch_num + total_batches - 1}: rows {offset:,} to {offset + rows_to_copy:,}...")

        retries = 0
        batch_success = False

        while retries <= MAX_RETRIES and not batch_success:
            try:
                if retries > 0:
                    print(f"  Retry {retries}/{MAX_RETRIES}...")
                    # Reconnect after error
                    try:
                        md_conn.close()
                        local_conn.close()
                    except:
                        pass
                    local_conn = duckdb.connect(LOCAL_DB_PATH, read_only=True)
                    md_conn = duckdb.connect(MOTHERDUCK_DB)
                    try:
                        md_conn.execute("DETACH local_db")
                    except:
                        pass
                    md_conn.execute(f"ATTACH '{LOCAL_DB_PATH}' AS local_db (READ_ONLY)")

                # Use INSERT with LIMIT/OFFSET
                insert_sql = f"""
                    INSERT INTO {table_name}
                    SELECT * FROM local_db.{table_name}
                    LIMIT {rows_to_copy} OFFSET {offset}
                """
                md_conn.execute(insert_sql)

                elapsed = time.time() - batch_start
                rows_per_sec = rows_to_copy / elapsed if elapsed > 0 else 0
                remaining = total_rows - offset - rows_to_copy
                eta_seconds = remaining / rows_per_sec if rows_per_sec > 0 else 0
                eta_minutes = eta_seconds / 60

                print(f"  ✓ Done in {elapsed:.1f}s ({rows_per_sec:,.0f} rows/sec)")
                print(f"  Remaining: {remaining:,} rows (~{eta_minutes:.1f} min)")

                offset += rows_to_copy
                batch_num += 1
                batch_success = True

            except Exception as e:
                error_str = str(e).lower()
                # Check for retryable errors (lease expired, connection issues)
                if 'lease expired' in error_str or 'connection' in error_str:
                    retries += 1
                    if retries <= MAX_RETRIES:
                        print(f"  ⚠ {e}")
                        print(f"  Sleeping {RETRY_DELAY}s before retry...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"  ✗ Error after {MAX_RETRIES} retries: {e}")
                        print(f"\n  To resume, run:")
                        print(f"  python scripts/upload_to_motherduck.py --table {table_name} --resume {offset}")
                        md_conn.close()
                        local_conn.close()
                        return  # Exit the function
                else:
                    # Non-retryable error
                    print(f"  ✗ Error: {e}")
                    print(f"\n  To resume, run:")
                    print(f"  python scripts/upload_to_motherduck.py --table {table_name} --resume {offset}")
                    md_conn.close()
                    local_conn.close()
                    return  # Exit the function

        if not batch_success:
            break

        # Close connections after each successful batch
        md_conn.close()
        local_conn.close()

    if offset >= total_rows:
        print(f"\n✓ Upload complete! {total_rows:,} rows uploaded to {table_name}")

def main():
    parser = argparse.ArgumentParser(description='Upload DuckDB to MotherDuck in batches')
    parser.add_argument('--batch-size', '--batch', type=int, default=1_000_000, dest='batch_size',
                        help='Rows per batch (default: 1M)')
    parser.add_argument('--table', choices=['albums', 'songs'], help='Upload specific table only')
    parser.add_argument('--resume', type=int, default=0, help='Resume from specific row offset')
    args = parser.parse_args()

    if args.table:
        upload_table(args.table, args.batch_size, args.resume)
    else:
        # Upload both tables
        upload_table('albums', args.batch_size)
        upload_table('songs', args.batch_size)

    print("\nDone!")

if __name__ == '__main__':
    main()
