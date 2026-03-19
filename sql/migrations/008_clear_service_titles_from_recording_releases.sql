-- ============================================================================
-- Migration: Clear service-sourced titles from recording_releases.track_title
-- Date: 2026-03-19
-- Description: recording_releases.track_title was populated by Spotify and
--              Apple Music matchers, but this column is intended for MusicBrainz
--              track titles. Service-specific titles now live in
--              recording_release_streaming_links.service_title (added in 007).
--              This clears the incorrectly-sourced values so the column can be
--              backfilled from MusicBrainz.
-- ============================================================================

-- VERIFICATION BEFORE:
-- SELECT COUNT(*) as has_track_title FROM recording_releases WHERE track_title IS NOT NULL;

-- Clear all track_title values (they all came from Spotify/Apple, not MB)
UPDATE recording_releases SET track_title = NULL WHERE track_title IS NOT NULL;

-- VERIFICATION AFTER:
-- SELECT COUNT(*) as has_track_title FROM recording_releases WHERE track_title IS NOT NULL;
-- Should be 0.
