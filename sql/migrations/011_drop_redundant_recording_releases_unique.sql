-- ============================================================================
-- Migration: Drop redundant 4-column UNIQUE on recording_releases, refresh
--            documentation comments on the dual MB-work-id columns.
-- Description:
--   recording_releases had two overlapping UNIQUE constraints:
--     (recording_id, release_id, disc_number, track_number)
--     (recording_id, release_id)
--   The two-column constraint is strictly stronger — any pair unique on its
--   own is automatically unique with extra columns. A spot check confirmed
--   no (recording_id, release_id) pair appears more than once in production:
--
--     SELECT recording_id, release_id, COUNT(*)
--     FROM recording_releases
--     GROUP BY recording_id, release_id
--     HAVING COUNT(*) > 1;
--     -- 0 rows
--
--   Drop the four-column constraint as redundant. Track/disc lookups are
--   already covered by idx_recording_releases_disc_track.
--
--   Also re-asserts the COMMENT ON COLUMN docs for songs.second_mb_id and
--   recordings.source_mb_work_id (originally added in migration 002) so that
--   any database bootstrapped from sql/jazz-db-schema.sql instead of run
--   through the migration sequence picks them up too. COMMENT ON COLUMN is
--   idempotent — safe to re-run.
--
-- Run: psql $DATABASE_URL -f sql/migrations/011_drop_redundant_recording_releases_unique.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- STEP 1: Drop the redundant 4-column UNIQUE constraint
-- ----------------------------------------------------------------------------
-- Find it dynamically by column composition rather than by auto-generated
-- name (the inline UNIQUE in CREATE TABLE produces a name we don't control).

DO $$
DECLARE
    redundant_constraint TEXT;
BEGIN
    SELECT con.conname INTO redundant_constraint
    FROM pg_constraint con
    JOIN pg_class cls ON cls.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
    WHERE nsp.nspname = 'public'
      AND cls.relname = 'recording_releases'
      AND con.contype = 'u'
      AND (
          SELECT array_agg(att.attname ORDER BY att.attname)
          FROM unnest(con.conkey) AS k(attnum)
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = k.attnum
      ) = ARRAY['disc_number', 'recording_id', 'release_id', 'track_number']::name[];

    IF redundant_constraint IS NULL THEN
        RAISE NOTICE 'Redundant 4-column UNIQUE on recording_releases not found — already dropped or never existed. Continuing.';
    ELSE
        EXECUTE format('ALTER TABLE recording_releases DROP CONSTRAINT %I', redundant_constraint);
        RAISE NOTICE 'Dropped UNIQUE constraint %', redundant_constraint;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- STEP 2: Verify the (recording_id, release_id) UNIQUE constraint still exists
-- ----------------------------------------------------------------------------

DO $$
DECLARE
    keep_count INTEGER;
BEGIN
    SELECT count(*) INTO keep_count
    FROM pg_constraint con
    JOIN pg_class cls ON cls.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
    WHERE nsp.nspname = 'public'
      AND cls.relname = 'recording_releases'
      AND con.contype = 'u'
      AND (
          SELECT array_agg(att.attname ORDER BY att.attname)
          FROM unnest(con.conkey) AS k(attnum)
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = k.attnum
      ) = ARRAY['recording_id', 'release_id']::name[];

    IF keep_count = 0 THEN
        RAISE EXCEPTION 'Expected UNIQUE(recording_id, release_id) constraint on recording_releases is missing. Aborting.';
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- STEP 3: (Re-)assert documentation comments on the dual MB-work-id columns
-- ----------------------------------------------------------------------------

COMMENT ON COLUMN songs.second_mb_id IS
    'Secondary MusicBrainz work ID for songs that exist as multiple works in MB '
    '(e.g., a standard split across two work entries, or an alternate version '
    'merged into a separate work). When set, recordings can be imported from '
    'either MB work and tracked via recordings.source_mb_work_id.';

COMMENT ON COLUMN recordings.source_mb_work_id IS
    'The MusicBrainz work ID this recording was imported from — either '
    'songs.musicbrainz_id or songs.second_mb_id. Used to assess which '
    'recordings came from the secondary MB work for review.';

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================
-- BEGIN;
-- ALTER TABLE recording_releases
--     ADD CONSTRAINT recording_releases_recording_id_release_id_disc_number_track_n_key
--     UNIQUE (recording_id, release_id, disc_number, track_number);
-- COMMIT;
