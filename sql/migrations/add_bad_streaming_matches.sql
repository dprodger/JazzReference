-- ============================================================================
-- Migration: Bad Streaming Match Blocklist
-- Description: Creates a blocklist table to prevent incorrect streaming service
--              matches from recurring. Supports blocking at track level (prevents
--              a streaming track from matching a song's recordings) and album
--              level (prevents a streaming album from matching a release).
-- ============================================================================

CREATE TABLE IF NOT EXISTS bad_streaming_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Streaming service identification
    service VARCHAR(50) NOT NULL,  -- 'spotify', 'apple_music', 'youtube_music', etc.

    -- Level of blocking: 'track' or 'album'
    -- 'track': blocks a specific track ID from matching recordings of this song
    -- 'album': blocks a specific album ID from matching releases of this song
    block_level VARCHAR(20) NOT NULL CHECK (block_level IN ('track', 'album')),

    -- The streaming service identifier being blocked
    service_id VARCHAR(100) NOT NULL,  -- e.g., Spotify track ID or album ID

    -- What it's being blocked FROM matching to
    -- song_id is required - this is the stable entity (recordings may be reimported)
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,

    -- Metadata
    reason TEXT,  -- Why this was marked as bad (e.g., "Wrong artist - Charles Bradley instead of Illinois Jacquet")

    -- Attribution (for future UI integration)
    reported_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Uniqueness: one entry per (service, block_level, service_id, song_id)
    CONSTRAINT bad_streaming_matches_unique UNIQUE (service, block_level, service_id, song_id)
);

-- Indexes for efficient lookups during matching
CREATE INDEX IF NOT EXISTS idx_bad_streaming_matches_service_id
    ON bad_streaming_matches(service, service_id);

CREATE INDEX IF NOT EXISTS idx_bad_streaming_matches_song_id
    ON bad_streaming_matches(song_id);

CREATE INDEX IF NOT EXISTS idx_bad_streaming_matches_lookup
    ON bad_streaming_matches(service, block_level, service_id, song_id);

-- Comments
COMMENT ON TABLE bad_streaming_matches IS
    'Blocklist for incorrect streaming service matches. Prevents specific track/album IDs '
    'from being matched to songs. Used by matchers to avoid recurring false positives.';

COMMENT ON COLUMN bad_streaming_matches.service IS
    'Streaming service: spotify, apple_music, youtube_music, tidal, amazon_music, etc.';

COMMENT ON COLUMN bad_streaming_matches.block_level IS
    'Level of blocking: track (blocks track ID from song recordings) or album (blocks album ID from song releases)';

COMMENT ON COLUMN bad_streaming_matches.service_id IS
    'The streaming service ID being blocked (track ID or album ID depending on block_level)';

COMMENT ON COLUMN bad_streaming_matches.song_id IS
    'The song this ID should NOT be matched to. Song is the stable entity since recordings may be reimported.';

COMMENT ON COLUMN bad_streaming_matches.reason IS
    'Human-readable explanation of why this match is incorrect (for documentation and future review)';

COMMENT ON COLUMN bad_streaming_matches.reported_by IS
    'User who reported this bad match (for future UI integration, NULL for manual entries)';
