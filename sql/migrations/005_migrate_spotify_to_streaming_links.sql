-- ============================================================================
-- Migration: Migrate Spotify Track Data to Normalized Streaming Links
-- Date: 2025-02-01
-- Description: Migrates spotify_track_id from recording_releases to the
--              normalized recording_release_streaming_links table, following
--              the pattern established for Apple Music.
-- ============================================================================

-- VERIFICATION BEFORE (run to capture counts):
-- SELECT COUNT(*) as spotify_tracks_legacy FROM recording_releases WHERE spotify_track_id IS NOT NULL;
-- SELECT COUNT(*) as spotify_tracks_normalized FROM recording_release_streaming_links WHERE service = 'spotify';

-- STEP 1: Migrate existing spotify_track_id data to recording_release_streaming_links
INSERT INTO recording_release_streaming_links (
    recording_release_id,
    service,
    service_id,
    service_url,
    matched_at,
    created_at
)
SELECT
    rr.id,
    'spotify',
    rr.spotify_track_id,
    'https://open.spotify.com/track/' || rr.spotify_track_id,
    rr.created_at,  -- Use original created_at as matched_at
    CURRENT_TIMESTAMP
FROM recording_releases rr
WHERE rr.spotify_track_id IS NOT NULL
ON CONFLICT (recording_release_id, service) DO NOTHING;

-- VERIFICATION AFTER (run to verify migration):
-- SELECT COUNT(*) as spotify_tracks_legacy FROM recording_releases WHERE spotify_track_id IS NOT NULL;
-- SELECT COUNT(*) as spotify_tracks_normalized FROM recording_release_streaming_links WHERE service = 'spotify';
-- Counts should match after migration.

-- ============================================================================
-- NOTE: The spotify_track_id column on recording_releases is NOT dropped yet.
-- This allows:
-- 1. Rollback if issues arise (code can be reverted to read from old column)
-- 2. Both old and new code to work during transition
--
-- To drop the column later (after verifying all code uses new table):
-- ALTER TABLE recording_releases DROP COLUMN spotify_track_id;
-- DROP INDEX IF EXISTS idx_recording_releases_spotify_track_id;
-- ============================================================================


SELECT COUNT(*) FROM recording_releases WHERE spotify_track_id IS NOT NULL;   
  SELECT COUNT(*) FROM recording_release_streaming_links WHERE service =        
  'spotify';    