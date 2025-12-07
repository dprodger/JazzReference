-- ============================================================================
-- Migration: Add Secondary MusicBrainz Work ID Support
-- Description: Adds support for songs that have multiple MusicBrainz work IDs,
--              and tracks which MB work ID each recording came from.
--
-- Background: Some songs exist as multiple works in MusicBrainz (e.g., different
--             versions or merged works). This allows importing recordings from
--             both work IDs while tracking the source for assessment.
--
-- Run: psql $DATABASE_URL -f sql/migrations/002_add_second_mb_id.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Add second_mb_id to songs table
-- ============================================================================

-- Secondary MusicBrainz work ID for songs that exist as multiple works
ALTER TABLE songs
ADD COLUMN IF NOT EXISTS second_mb_id VARCHAR(36);

-- ============================================================================
-- STEP 2: Add source_mb_work_id to recordings table
-- ============================================================================

-- Tracks which MusicBrainz work ID this recording was imported from
-- Allows assessment of recordings from secondary MB work IDs
ALTER TABLE recordings
ADD COLUMN IF NOT EXISTS source_mb_work_id VARCHAR(36);

-- ============================================================================
-- STEP 3: Add indexes for queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_songs_second_mb_id
    ON songs(second_mb_id)
    WHERE second_mb_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recordings_source_mb_work_id
    ON recordings(source_mb_work_id)
    WHERE source_mb_work_id IS NOT NULL;

-- ============================================================================
-- STEP 4: Add documentation comments
-- ============================================================================

COMMENT ON COLUMN songs.second_mb_id IS
    'Secondary MusicBrainz work ID for songs that exist as multiple works in MB. '
    'Used to import recordings from both work IDs.';

COMMENT ON COLUMN recordings.source_mb_work_id IS
    'The MusicBrainz work ID this recording was imported from. '
    'Allows tracking which recordings came from secondary work IDs for assessment.';

-- ============================================================================
-- STEP 5: Backfill source_mb_work_id for existing recordings
-- ============================================================================

-- Set source_mb_work_id for existing recordings to the song's primary musicbrainz_id
UPDATE recordings r
SET source_mb_work_id = s.musicbrainz_id
FROM songs s
WHERE r.song_id = s.id
  AND r.source_mb_work_id IS NULL
  AND s.musicbrainz_id IS NOT NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Uncomment to verify migration:
-- SELECT
--     COUNT(*) as total_songs,
--     COUNT(second_mb_id) as with_second_mb_id
-- FROM songs;

-- SELECT
--     COUNT(*) as total_recordings,
--     COUNT(source_mb_work_id) as with_source_mb_work_id
-- FROM recordings;

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
--
-- BEGIN;
-- ALTER TABLE songs DROP COLUMN IF EXISTS second_mb_id;
-- ALTER TABLE recordings DROP COLUMN IF EXISTS source_mb_work_id;
-- DROP INDEX IF EXISTS idx_songs_second_mb_id;
-- DROP INDEX IF EXISTS idx_recordings_source_mb_work_id;
-- COMMIT;

