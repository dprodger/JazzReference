-- ============================================================================
-- Migration: Add Recording Date Source Tracking
-- Description: Adds fields to track the source and precision of recording dates,
--              plus caches MusicBrainz first-release-date for reference.
--
-- Background: Recording dates should represent when the session occurred, not
--             when the album was released. This migration adds tracking so we
--             know where each date came from and can compute effective dates.
--
-- Run: psql $DATABASE_URL -f sql/migrations/001_add_recording_date_tracking.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Add new columns to recordings table
-- ============================================================================

-- Source of the recording date (where did we get this information?)
-- Values: 'mb_performer_relation', 'mb_first_release', 'earliest_release', 'manual'
ALTER TABLE recordings
ADD COLUMN IF NOT EXISTS recording_date_source VARCHAR(50);

-- Precision of the recording date
-- Values: 'day' (full YYYY-MM-DD), 'month' (YYYY-MM), 'year' (YYYY only)
ALTER TABLE recordings
ADD COLUMN IF NOT EXISTS recording_date_precision VARCHAR(10);

-- Cache MusicBrainz's first-release-date for this recording
-- Stored as VARCHAR to preserve original precision (YYYY, YYYY-MM, or YYYY-MM-DD)
-- This is an upper bound - recording can't be later than first release
ALTER TABLE recordings
ADD COLUMN IF NOT EXISTS mb_first_release_date VARCHAR(10);

-- ============================================================================
-- STEP 2: Add indexes for common queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_recordings_recording_date_source
    ON recordings(recording_date_source)
    WHERE recording_date_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recordings_mb_first_release_date
    ON recordings(mb_first_release_date)
    WHERE mb_first_release_date IS NOT NULL;

-- ============================================================================
-- STEP 3: Add documentation comments
-- ============================================================================

COMMENT ON COLUMN recordings.recording_date IS
    'Best known recording session date. Source tracked in recording_date_source.';

COMMENT ON COLUMN recordings.recording_year IS
    'Recording year - may be more reliable than full date when precision is limited.';

COMMENT ON COLUMN recordings.recording_date_source IS
    'Source of recording_date: mb_performer_relation (session dates from credits), '
    'mb_first_release (MusicBrainz first-release-date), earliest_release (computed from releases), '
    'manual (explicitly set).';

COMMENT ON COLUMN recordings.recording_date_precision IS
    'Precision of recording_date: day (YYYY-MM-DD known), month (YYYY-MM known), year (YYYY only).';

COMMENT ON COLUMN recordings.mb_first_release_date IS
    'MusicBrainz first-release-date for this recording (cached). '
    'Preserves original precision as YYYY, YYYY-MM, or YYYY-MM-DD. '
    'Serves as upper bound - recording cannot be later than first release.';

-- ============================================================================
-- STEP 4: Mark existing dates as needing review
-- ============================================================================

-- Existing dates came from release dates (not actual recording dates)
-- Mark them so we know they need to be re-evaluated
-- Only mark rows that have dates but no source yet
UPDATE recordings
SET recording_date_source = 'legacy_release_date'
WHERE (recording_date IS NOT NULL OR recording_year IS NOT NULL)
  AND recording_date_source IS NULL;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Uncomment to verify migration:
-- SELECT
--     COUNT(*) as total_recordings,
--     COUNT(recording_date_source) as with_source,
--     COUNT(recording_date_precision) as with_precision,
--     COUNT(mb_first_release_date) as with_mb_first_release
-- FROM recordings;

-- SELECT recording_date_source, COUNT(*)
-- FROM recordings
-- GROUP BY recording_date_source;

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
--
-- BEGIN;
-- ALTER TABLE recordings DROP COLUMN IF EXISTS recording_date_source;
-- ALTER TABLE recordings DROP COLUMN IF EXISTS recording_date_precision;
-- ALTER TABLE recordings DROP COLUMN IF EXISTS mb_first_release_date;
-- DROP INDEX IF EXISTS idx_recordings_recording_date_source;
-- DROP INDEX IF EXISTS idx_recordings_mb_first_release_date;
-- COMMIT;

ROLLBACK;