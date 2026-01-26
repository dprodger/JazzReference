-- Migration: Add title column to recordings table
-- Date: 2025-01-26
-- Description: Add title column to store MusicBrainz recording title (may differ from song title)

-- Add the title column
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS title VARCHAR(500);

-- Create index for title searches
CREATE INDEX IF NOT EXISTS idx_recordings_title ON recordings(title);

-- Add column comment
COMMENT ON COLUMN recordings.title IS 'Recording title from MusicBrainz (may differ from song title)';

-- Note: recording_releases.track_title column already exists (VARCHAR(500))
-- No schema change needed there - it will be populated by Spotify/Apple Music matchers
