-- ============================================================================
-- Migration: Add unique constraint on recordings(musicbrainz_id, song_id)
-- Description: Prevents duplicate recordings for the same MusicBrainz recording
--              under the same song. Different songs may share a MB recording ID
--              (medleys, multi-work recordings) so the constraint is per-song.
--
-- Prerequisites: Run scripts/deduplicate_recordings.py first to clean up
--               existing duplicates.
--
-- Run: psql $DATABASE_URL -f sql/migrations/010_add_unique_recording_mb_id_song_id.sql
-- ============================================================================

BEGIN;

-- Verify no duplicates remain
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT count(*) INTO dup_count
    FROM (
        SELECT musicbrainz_id, song_id
        FROM recordings
        WHERE musicbrainz_id IS NOT NULL
        GROUP BY musicbrainz_id, song_id
        HAVING count(*) > 1
    ) dups;

    IF dup_count > 0 THEN
        RAISE EXCEPTION 'Found % duplicate (musicbrainz_id, song_id) groups. Run scripts/deduplicate_recordings.py first.', dup_count;
    END IF;
END $$;

-- Add the unique constraint (partial — only for non-null musicbrainz_id)
CREATE UNIQUE INDEX idx_recordings_mb_id_song_id
    ON recordings (musicbrainz_id, song_id)
    WHERE musicbrainz_id IS NOT NULL;

COMMIT;
