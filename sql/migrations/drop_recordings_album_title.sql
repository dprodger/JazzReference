-- Migration: Drop album_title column from recordings table
-- Date: 2024-12-22
--
-- This column is deprecated. Album titles should now come from the
-- recording's default release (recordings.default_release_id -> releases.title).
--
-- Before running this migration, ensure:
-- 1. All code references to recordings.album_title have been updated
-- 2. All recordings have a default_release_id set (or you accept NULL album titles)

-- ============================================================================
-- PRE-MIGRATION CHECK: Verify recordings have default releases
-- ============================================================================

-- Check how many recordings would lose their album title
-- (have album_title but no default_release_id)
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM recordings r
    WHERE r.album_title IS NOT NULL
      AND r.default_release_id IS NULL;

    IF orphan_count > 0 THEN
        RAISE WARNING '% recordings have album_title but no default_release_id - these will lose their album title', orphan_count;
    END IF;
END $$;

-- ============================================================================
-- BACKUP: Create a backup table with the album_title data (optional safety net)
-- ============================================================================

-- Uncomment the following if you want to preserve the data before dropping:
/*
CREATE TABLE IF NOT EXISTS _backup_recordings_album_title AS
SELECT id, album_title, default_release_id
FROM recordings
WHERE album_title IS NOT NULL;

COMMENT ON TABLE _backup_recordings_album_title IS
    'Backup of recordings.album_title before column was dropped. Created 2024-12-22. Safe to drop after verifying migration.';
*/

-- ============================================================================
-- MIGRATION: Drop the column
-- ============================================================================

ALTER TABLE recordings DROP COLUMN IF EXISTS album_title CASCADE;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'recordings' AND column_name = 'album_title'
    ) THEN
        RAISE EXCEPTION 'Migration failed: album_title column still exists';
    ELSE
        RAISE NOTICE 'Migration successful: album_title column has been dropped from recordings table';
    END IF;
END $$;
