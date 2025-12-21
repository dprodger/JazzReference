# Alternative Approaches for Apple Music Catalog Hosting

**Created:** 2024-12-21
**Status:** Exploring options
**Current approach:** MotherDuck (attempting upload)

## Problem Statement

The Apple Music matcher needs access to a ~40-50GB DuckDB database containing the Apple Music catalog (downloaded via Feed API). Requirements:

1. **Accessible from laptop** - for debugging and ad-hoc scripts
2. **Accessible from Render server** - for background song research queue (always-on)
3. **Fast and cost-effective**

### Current Approaches Tried

| Approach | Pros | Cons |
|----------|------|------|
| Local DuckDB on laptop | Fast, all local | Not always-on, 40-50GB disk |
| MotherDuck | Works from both places | Slower than local, trouble uploading large DB |

---

## Option 1: Cheap VPS with DuckDB API Service

Spin up a Hetzner/DigitalOcean/Linode VPS with 80-100GB SSD.

### Architecture

```
┌─────────────┐     ┌─────────────┐
│   Laptop    │     │   Render    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │ HTTP API
         ┌───────▼───────┐
         │  VPS ($5-10)  │
         │  DuckDB +     │
         │  Flask/Fast   │
         └───────────────┘
```

### Setup

1. Provision VPS (e.g., Hetzner CAX11 ~€4/mo: 2 ARM cores, 4GB RAM, 40GB disk + extra volume)
2. Install DuckDB + simple Flask wrapper
3. SCP the parquet files or DuckDB database
4. Expose search endpoints

### Estimated Performance

- ~50-100ms per query (local SSD)
- Always-on
- Cost: ~$5-10/month

### Pros/Cons

- **Pros:** Very fast, always-on, cheap
- **Cons:** Another service to maintain, need to handle updates

---

## Option 2: Cloudflare R2 + DuckDB httpfs (DETAILED)

Store parquet files in Cloudflare R2, query directly using DuckDB's httpfs extension.

### Architecture

```
┌─────────────┐     ┌─────────────┐
│   Laptop    │     │   Render    │
│  (scripts)  │     │  (API/queue)│
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  DuckDB httpfs    │
       │  (S3 protocol)    │
       └─────────┬─────────┘
                 │
         ┌───────▼───────┐
         │ Cloudflare R2 │
         │  (parquet)    │
         │  ~40-50GB     │
         └───────────────┘
```

### Setup Steps

#### 1. Create R2 bucket and API token

In Cloudflare dashboard:
- Create bucket: `apple-music-catalog`
- Create API token with read/write access to R2
- Note down: account ID, access key ID, secret access key

#### 2. Upload parquet files

```bash
# Using rclone (recommended for large files)
rclone config  # Set up R2 remote called "r2"

# Sync albums
rclone sync backend/data/apple_music_catalog/albums/2024-12-20/ \
  r2:apple-music-catalog/albums/

# Sync songs (if using)
rclone sync backend/data/apple_music_catalog/songs/2024-12-20/ \
  r2:apple-music-catalog/songs/

# Or using aws cli
aws s3 sync backend/data/apple_music_catalog/albums/2024-12-20/ \
  s3://apple-music-catalog/albums/ \
  --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

#### 3. Environment variables

Add to `.env`:
```bash
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET=apple-music-catalog
```

#### 4. DuckDB connection code

```python
import os
import duckdb

def get_r2_connection():
    """Get a DuckDB connection configured for R2 access."""
    conn = duckdb.connect()
    conn.execute("INSTALL httpfs; LOAD httpfs;")

    account_id = os.environ['R2_ACCOUNT_ID']
    access_key = os.environ['R2_ACCESS_KEY_ID']
    secret_key = os.environ['R2_SECRET_ACCESS_KEY']

    conn.execute(f"""
        SET s3_region='auto';
        SET s3_endpoint='{account_id}.r2.cloudflarestorage.com';
        SET s3_access_key_id='{access_key}';
        SET s3_secret_access_key='{secret_key}';
        SET s3_url_style='path';
    """)
    return conn


def search_albums_r2(artist_name: str, album_title: str, limit: int = 25):
    """Search albums directly from R2 parquet files."""
    conn = get_r2_connection()
    bucket = os.environ['R2_BUCKET']

    conditions = []
    if artist_name:
        conditions.append(f"LOWER(CAST(primaryArtists AS VARCHAR)) LIKE '%{artist_name.lower()}%'")
    if album_title:
        conditions.append(f"LOWER(nameDefault) LIKE '%{album_title.lower()}%'")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            id,
            nameDefault as name,
            primaryArtists[1].name as artistName,
            CAST(releaseDate AS VARCHAR) as releaseDate,
            len(songs) as trackCount,
            upc
        FROM read_parquet('s3://{bucket}/albums/*.parquet')
        WHERE {where_clause}
        LIMIT {limit}
    """

    return conn.execute(query).fetchall()
```

### Sub-options for Performance

#### A) Raw Parquet (Simple but Slow)

Just upload parquet files and query them directly.

- **Setup:** Simple - just upload files
- **Performance:** 2-10 seconds per query (full scan over network)
- **Best for:** Infrequent queries, batch processing

#### B) Upload Indexed DuckDB File

Upload the pre-indexed `apple_music_catalog.duckdb` file.

```python
# DuckDB can attach remote databases (experimental)
conn = duckdb.connect()
conn.execute("INSTALL httpfs; LOAD httpfs;")
# ... set S3 credentials ...
conn.execute("ATTACH 's3://bucket/apple_music_catalog.duckdb' AS catalog (READ_ONLY);")
```

- **Performance:** Faster for indexed queries
- **Caveat:** DuckDB remote DB support is still maturing

#### C) Partitioned Parquet + Small Index (Best Performance)

Create a small index file for quick lookups, partition data by artist initial.

```
s3://apple-music-catalog/
├── albums/
│   ├── artist_a/*.parquet   # Albums where artist starts with 'a'
│   ├── artist_b/*.parquet
│   └── ...
└── index/
    └── artist_album_index.parquet  # Small: just id, artist, album name (~500MB)
```

Query flow:
1. Search small index file for matching IDs
2. Fetch only relevant partitions

### Performance Estimates

| Approach | Per-query | 100 releases | Notes |
|----------|-----------|--------------|-------|
| Local DuckDB | ~50ms | ~5 sec | Baseline |
| MotherDuck | ~200-500ms | ~20-50 sec | Current |
| R2 raw parquet | ~2-5 sec | ~3-8 min | Probably too slow |
| R2 with index | ~300-800ms | ~30-80 sec | Comparable to MotherDuck |

### Cost

- **Storage:** ~$0.015/GB/month = ~$0.75/month for 50GB
- **Egress:** FREE (R2's main advantage over S3)
- **Operations:** $0.36 per million Class A, $0.36 per million Class B

### Pros/Cons

- **Pros:** No server to maintain, very cheap, free egress
- **Cons:** Slower than local, need to test real-world performance

### Testing Script (TODO)

Before committing, test with a subset:

```python
# TODO: Create test script that:
# 1. Uploads a few parquet files to R2
# 2. Runs benchmark queries (10-20 typical searches)
# 3. Measures and reports latency
# 4. Compares to local DuckDB baseline
```

---

## Option 3: Fly.io with Volume

Similar to VPS but with nicer deployment model.

### Setup

```bash
fly launch --name apple-music-catalog
fly volumes create catalog_data --size 60 --region ord
# Deploy Flask + DuckDB app
```

### Pros/Cons

- **Pros:** Easy deploys, can scale to zero
- **Cons:** Volume pricing (~$0.15/GB/month = ~$9/month for 60GB)

---

## Option 4: PostgreSQL (Existing DB)

Load the catalog into your existing Render PostgreSQL.

### Setup

```sql
-- Create tables
CREATE TABLE apple_albums (
    id TEXT PRIMARY KEY,
    name TEXT,
    artist_name TEXT,
    release_date DATE,
    track_count INT,
    upc TEXT
);

CREATE TABLE apple_songs (
    id TEXT PRIMARY KEY,
    name TEXT,
    artist_name TEXT,
    album_id TEXT,
    disc_number INT,
    track_number INT,
    duration_ms INT,
    isrc TEXT
);

-- Add indexes for fuzzy search
CREATE INDEX idx_albums_artist_lower ON apple_albums (LOWER(artist_name));
CREATE INDEX idx_albums_name_lower ON apple_albums (LOWER(name));
CREATE INDEX idx_songs_album ON apple_songs (album_id);

-- Or use trigram indexes for better LIKE performance
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_albums_artist_trgm ON apple_albums USING gin (artist_name gin_trgm_ops);
CREATE INDEX idx_albums_name_trgm ON apple_albums USING gin (name gin_trgm_ops);
```

### Pros/Cons

- **Pros:** No new infrastructure, already accessible everywhere
- **Cons:** 40GB more in your DB, may need to upgrade Render plan, Postgres LIKE might be slower than DuckDB

---

## Decision Matrix

| Factor | VPS | R2+httpfs | Fly.io | PostgreSQL |
|--------|-----|-----------|--------|------------|
| Speed | Excellent | Good-ish | Excellent | Good |
| Always-on | Yes | Yes | Yes | Yes |
| Maintenance | Low | None | Low | None |
| Cost/month | ~$6 | ~$1 | ~$9 | $0 (existing) |
| Setup effort | Medium | Medium | Medium | High |
| Data updates | SCP files | Upload to R2 | SCP files | ETL script |

---

## Next Steps

1. [ ] Finish MotherDuck upload attempt
2. [ ] If MotherDuck doesn't work out, test R2 + httpfs performance
3. [ ] Based on R2 results, decide between R2 and VPS
4. [ ] Implement chosen solution
5. [ ] Update `apple_music_feed.py` to support new backend
