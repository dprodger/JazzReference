-- Orphan Recordings Table
-- Stores MusicBrainz recordings that match song titles but lack work relationships
-- Used for manual review and selective import into the main recordings table

CREATE TABLE IF NOT EXISTS orphan_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Link to our song
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,

    -- MusicBrainz recording data
    mb_recording_id VARCHAR(36) NOT NULL,
    mb_recording_title VARCHAR(500),
    mb_artist_credit VARCHAR(500),          -- Combined artist credit string
    mb_artist_ids TEXT[],                    -- Array of MB artist IDs
    mb_first_release_date VARCHAR(20),       -- YYYY, YYYY-MM, or YYYY-MM-DD
    mb_release_count INTEGER,                -- Number of releases this recording appears on
    mb_length_ms INTEGER,                    -- Duration in milliseconds
    mb_disambiguation VARCHAR(500),          -- MB disambiguation text if any

    -- Spotify match data (populated by enrichment step)
    spotify_track_id VARCHAR(100),
    spotify_track_name VARCHAR(500),
    spotify_artist_name VARCHAR(500),
    spotify_album_name VARCHAR(500),
    spotify_album_id VARCHAR(100),
    spotify_preview_url VARCHAR(500),        -- 30-second preview URL
    spotify_external_url VARCHAR(500),       -- Link to open in Spotify
    spotify_album_art_url VARCHAR(500),
    spotify_match_confidence VARCHAR(20),    -- 'high', 'medium', 'low', 'none'
    spotify_match_score FLOAT,               -- Similarity score 0-100
    spotify_matched_at TIMESTAMP WITH TIME ZONE,

    -- Issue type
    issue_type VARCHAR(50) NOT NULL,         -- 'no_work_link', 'wrong_work'
    linked_work_ids TEXT[],                  -- For 'wrong_work' - which works it's linked to

    -- Review status
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'approved', 'rejected', 'imported'
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(100),
    review_notes TEXT,

    -- Import tracking
    imported_recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    imported_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(song_id, mb_recording_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_orphan_recordings_song_id ON orphan_recordings(song_id);
CREATE INDEX IF NOT EXISTS idx_orphan_recordings_status ON orphan_recordings(status);
CREATE INDEX IF NOT EXISTS idx_orphan_recordings_mb_recording_id ON orphan_recordings(mb_recording_id);
CREATE INDEX IF NOT EXISTS idx_orphan_recordings_spotify_match ON orphan_recordings(spotify_match_confidence);

-- Comments
COMMENT ON TABLE orphan_recordings IS 'MusicBrainz recordings matching song titles but lacking proper work relationships';
COMMENT ON COLUMN orphan_recordings.issue_type IS 'no_work_link = no relationship to any work; wrong_work = linked to different work';
COMMENT ON COLUMN orphan_recordings.status IS 'pending = needs review; approved = good match; rejected = not relevant; imported = added to recordings table';
COMMENT ON COLUMN orphan_recordings.spotify_match_confidence IS 'high = exact match; medium = fuzzy match; low = weak match; none = no match found';
