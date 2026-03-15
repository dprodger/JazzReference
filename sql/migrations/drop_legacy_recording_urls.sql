-- Migration: Remove legacy youtube_url and apple_music_url from recordings table
-- These have been replaced by recording_release_streaming_links
--
-- Before running this migration, verify no orphaned data exists:
--   SELECT r.id, r.title, r.youtube_url, s.title as song
--   FROM recordings r JOIN songs s ON r.song_id = s.id
--   WHERE r.youtube_url IS NOT NULL
--     AND NOT EXISTS (
--         SELECT 1 FROM recording_releases rr
--         JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr.id
--         WHERE rr.recording_id = r.id AND rrsl.service = 'youtube'
--     );
--
-- As of 2026-03-15, there is 1 orphan: recording 023ff8af (Once I Loved)
-- with youtube_url https://www.youtube.com/watch?v=AYt-qpnYWQk
-- Manually add this via the app's "Add Streaming Link" feature before running.

-- Drop the columns
ALTER TABLE recordings DROP COLUMN IF EXISTS youtube_url;
ALTER TABLE recordings DROP COLUMN IF EXISTS apple_music_url;

-- Update the view that referenced youtube_url
CREATE OR REPLACE VIEW songs_with_canonical_recordings AS
SELECT
    s.id as song_id,
    s.title,
    s.composer,
    r.id as canonical_recording_id,
    r.album_title,
    r.recording_year,
    r.spotify_url
FROM songs s
LEFT JOIN recordings r ON s.id = r.song_id AND r.is_canonical = true;
