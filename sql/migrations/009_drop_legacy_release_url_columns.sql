-- ============================================================================
-- Migration: Drop Legacy URL Columns from releases
-- Description: Remove spotify_album_url and apple_music_url from releases.
--              spotify_album_url is redundant (constructable from spotify_album_id).
--              apple_music_url is empty and superseded by release_streaming_links.
--
-- Run: psql $DATABASE_URL -f sql/migrations/009_drop_legacy_release_url_columns.sql
-- ============================================================================

BEGIN;

-- Drop both columns
ALTER TABLE releases DROP COLUMN IF EXISTS spotify_album_url;
ALTER TABLE releases DROP COLUMN IF EXISTS apple_music_url;

-- Verify
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'releases' AND column_name IN ('spotify_album_url', 'apple_music_url')
    ) THEN
        RAISE EXCEPTION 'Legacy URL columns still exist in releases table';
    END IF;

    RAISE NOTICE 'Migration successful: spotify_album_url and apple_music_url dropped from releases';
END $$;

COMMIT;
