-- Add duration_ms to recordings table
-- Stores the recording duration in milliseconds from MusicBrainz
-- This is the canonical duration for the recording itself, separate from
-- per-track durations in recording_release_streaming_links

ALTER TABLE recordings ADD COLUMN duration_ms INTEGER;
