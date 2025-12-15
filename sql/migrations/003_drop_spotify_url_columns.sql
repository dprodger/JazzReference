-- ============================================================================
-- Migration: Drop Redundant Spotify URL Columns
-- Description: Remove spotify_album_url and spotify_track_url columns since
--              URLs are deterministic and can be constructed from IDs:
--              - Album: https://open.spotify.com/album/{spotify_album_id}
--              - Track: https://open.spotify.com/track/{spotify_track_id}
--
-- Benefits:
--   - Single source of truth (IDs are Spotify's canonical identifiers)
--   - No sync risk (can't have mismatched ID/URL pairs)
--   - Simpler importers (only need to write one column)
--
-- Prerequisites: Application code must be updated to construct URLs from IDs
--                before running this migration.
--
-- Run: psql $DATABASE_URL -f sql/migrations/003_drop_spotify_url_columns.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Verify no data inconsistencies before dropping
-- ============================================================================

-- Check for any URL/ID mismatches in releases (should return 0 rows)
DO $$
DECLARE
    mismatch_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO mismatch_count
    FROM releases
    WHERE spotify_album_url IS NOT NULL
      AND spotify_album_id IS NOT NULL
      AND spotify_album_url <> 'https://open.spotify.com/album/' || spotify_album_id;

    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Found % releases with mismatched spotify_album_url/id pairs. Please fix before migrating.', mismatch_count;
    END IF;
END $$;

-- Check for any URL/ID mismatches in recording_releases (should return 0 rows)
DO $$
DECLARE
    mismatch_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO mismatch_count
    FROM recording_releases
    WHERE spotify_track_url IS NOT NULL
      AND spotify_track_id IS NOT NULL
      AND spotify_track_url <> 'https://open.spotify.com/track/' || spotify_track_id;

    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Found % recording_releases with mismatched spotify_track_url/id pairs. Please fix before migrating.', mismatch_count;
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Drop the URL columns
-- ============================================================================

-- Drop spotify_album_url from releases table
ALTER TABLE releases
DROP COLUMN IF EXISTS spotify_album_url;

-- Drop spotify_track_url from recording_releases table
ALTER TABLE recording_releases
DROP COLUMN IF EXISTS spotify_track_url;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify columns are dropped
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'releases' AND column_name = 'spotify_album_url'
    ) THEN
        RAISE EXCEPTION 'spotify_album_url column still exists in releases table';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'recording_releases' AND column_name = 'spotify_track_url'
    ) THEN
        RAISE EXCEPTION 'spotify_track_url column still exists in recording_releases table';
    END IF;

    RAISE NOTICE 'Migration successful: URL columns dropped';
END $$;

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed - requires data restoration from backup)
-- ============================================================================
--
-- Note: Rollback requires restoring data from backup since URLs are not stored.
-- The URLs can be reconstructed from IDs if needed:
--
-- BEGIN;
-- ALTER TABLE releases ADD COLUMN spotify_album_url TEXT;
-- ALTER TABLE recording_releases ADD COLUMN spotify_track_url TEXT;
--
-- UPDATE releases
-- SET spotify_album_url = 'https://open.spotify.com/album/' || spotify_album_id
-- WHERE spotify_album_id IS NOT NULL;
--
-- UPDATE recording_releases
-- SET spotify_track_url = 'https://open.spotify.com/track/' || spotify_track_id
-- WHERE spotify_track_id IS NOT NULL;
-- COMMIT;
