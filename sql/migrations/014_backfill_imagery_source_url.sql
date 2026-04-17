-- ============================================================================
-- Migration: Backfill release_imagery.source_url for Spotify and Apple images
-- Description:
--   The Spotify and Apple Music importers did not originally populate
--   release_imagery.source_url. The import code has since been fixed
--   (see backend/integrations/spotify/db.py and .../apple_music/db.py —
--   both now compute the URL from source_id on UPSERT), but pre-existing
--   rows still have source_url = NULL, which breaks the attribution link
--   in the app.
--
--   As of the last audit, ~27,984 Spotify rows and ~3,860 Apple rows are
--   affected (closes #87).
--
--   source_url is deterministic from source + source_id:
--     Spotify: https://open.spotify.com/album/{source_id}
--     Apple:   https://music.apple.com/album/{source_id}
--
-- Idempotent: only rewrites rows where source_url IS NULL, so safe to
-- re-run.
--
-- Run: psql $DATABASE_URL -f sql/migrations/014_backfill_imagery_source_url.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- STEP 1: Backfill Spotify source_url
-- ----------------------------------------------------------------------------

WITH updated AS (
    UPDATE release_imagery
    SET source_url = 'https://open.spotify.com/album/' || source_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE source = 'Spotify'
      AND source_id IS NOT NULL
      AND source_url IS NULL
    RETURNING 1
)
SELECT 'Spotify rows backfilled: ' || count(*) AS result FROM updated;

-- ----------------------------------------------------------------------------
-- STEP 2: Backfill Apple Music source_url
-- ----------------------------------------------------------------------------

WITH updated AS (
    UPDATE release_imagery
    SET source_url = 'https://music.apple.com/album/' || source_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE source = 'Apple'
      AND source_id IS NOT NULL
      AND source_url IS NULL
    RETURNING 1
)
SELECT 'Apple rows backfilled: ' || count(*) AS result FROM updated;

-- ----------------------------------------------------------------------------
-- STEP 3: Verify no remaining NULL source_url where we can derive it
-- ----------------------------------------------------------------------------
-- Rows with source_id IS NULL are left alone — we can't derive a URL for
-- them. Anything else that's still NULL after the updates above is a bug.

DO $$
DECLARE
    stranded_count INTEGER;
BEGIN
    SELECT count(*) INTO stranded_count
    FROM release_imagery
    WHERE source IN ('Spotify', 'Apple')
      AND source_id IS NOT NULL
      AND source_url IS NULL;

    IF stranded_count > 0 THEN
        RAISE EXCEPTION
            'Backfill left % Spotify/Apple rows with source_id but no source_url — aborting.',
            stranded_count;
    END IF;

    RAISE NOTICE 'Verification passed: every Spotify/Apple row with source_id now has source_url.';
END $$;

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
-- The backfill is deterministic from source_id, so re-running is a no-op
-- rather than destructive. To undo for testing, null out what we set:
--
-- BEGIN;
-- UPDATE release_imagery
-- SET source_url = NULL
-- WHERE source = 'Spotify'
--   AND source_url = 'https://open.spotify.com/album/' || source_id;
-- UPDATE release_imagery
-- SET source_url = NULL
-- WHERE source = 'Apple'
--   AND source_url = 'https://music.apple.com/album/' || source_id;
-- COMMIT;
