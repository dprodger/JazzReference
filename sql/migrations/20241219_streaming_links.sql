-- ============================================================================
-- Migration: Add Streaming Service Links (Normalized)
-- Date: 2024-12-19
-- Description: Creates normalized tables for streaming service links (Spotify,
--              Apple Music, YouTube, etc.) instead of per-service columns.
-- ============================================================================

-- STEP 1: Create release_streaming_links table (album-level)
CREATE TABLE IF NOT EXISTS release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,
    service_id VARCHAR(100),
    service_url VARCHAR(500),
    match_confidence DECIMAL(3,2),
    match_method VARCHAR(100),
    matched_at TIMESTAMP WITH TIME ZONE,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT release_streaming_links_unique UNIQUE (release_id, service)
);

-- STEP 2: Indexes for release_streaming_links
CREATE INDEX IF NOT EXISTS idx_release_streaming_links_release_id
    ON release_streaming_links(release_id);

CREATE INDEX IF NOT EXISTS idx_release_streaming_links_service
    ON release_streaming_links(service);

CREATE INDEX IF NOT EXISTS idx_release_streaming_links_service_id
    ON release_streaming_links(service_id)
    WHERE service_id IS NOT NULL;

-- STEP 3: Trigger for release_streaming_links updated_at
CREATE OR REPLACE FUNCTION update_release_streaming_links_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_release_streaming_links_updated_at ON release_streaming_links;
CREATE TRIGGER trigger_release_streaming_links_updated_at
    BEFORE UPDATE ON release_streaming_links
    FOR EACH ROW
    EXECUTE FUNCTION update_release_streaming_links_updated_at();

-- STEP 4: Create recording_release_streaming_links table (track-level)
CREATE TABLE IF NOT EXISTS recording_release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_release_id UUID NOT NULL REFERENCES recording_releases(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,
    service_id VARCHAR(100),
    service_url VARCHAR(500),
    duration_ms INTEGER,
    popularity INTEGER,
    preview_url VARCHAR(500),
    isrc VARCHAR(20),
    match_confidence DECIMAL(3,2),
    match_method VARCHAR(100),
    matched_at TIMESTAMP WITH TIME ZONE,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT recording_release_streaming_links_unique UNIQUE (recording_release_id, service)
);

-- STEP 5: Indexes for recording_release_streaming_links
CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_recording_release_id
    ON recording_release_streaming_links(recording_release_id);

CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_service
    ON recording_release_streaming_links(service);

CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_service_id
    ON recording_release_streaming_links(service_id)
    WHERE service_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_isrc
    ON recording_release_streaming_links(isrc)
    WHERE isrc IS NOT NULL;

-- STEP 6: Trigger for recording_release_streaming_links updated_at
CREATE OR REPLACE FUNCTION update_rr_streaming_links_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_rr_streaming_links_updated_at ON recording_release_streaming_links;
CREATE TRIGGER trigger_rr_streaming_links_updated_at
    BEFORE UPDATE ON recording_release_streaming_links
    FOR EACH ROW
    EXECUTE FUNCTION update_rr_streaming_links_updated_at();

-- STEP 7: Add documentation comments
COMMENT ON TABLE release_streaming_links IS
    'Normalized table for streaming service album links. One row per (release, service) pair.';

COMMENT ON COLUMN release_streaming_links.service IS
    'Streaming service identifier: spotify, apple_music, youtube_music, tidal, amazon_music, deezer, etc.';

COMMENT ON COLUMN release_streaming_links.service_id IS
    'Album/collection ID on this service (e.g., Spotify album ID, Apple Music collection ID)';

COMMENT ON COLUMN release_streaming_links.match_confidence IS
    'Confidence score 0.00-1.00 indicating how certain we are this is the correct album';

COMMENT ON COLUMN release_streaming_links.match_method IS
    'Method used to match: fuzzy_search, isrc_lookup, upc_lookup, manual, etc.';

COMMENT ON TABLE recording_release_streaming_links IS
    'Normalized table for streaming service track links. One row per (recording_release, service) pair.';

COMMENT ON COLUMN recording_release_streaming_links.service IS
    'Streaming service identifier: spotify, apple_music, youtube_music, tidal, amazon_music, deezer, etc.';

COMMENT ON COLUMN recording_release_streaming_links.service_id IS
    'Track/song ID on this service (e.g., Spotify track ID, Apple Music song ID)';

COMMENT ON COLUMN recording_release_streaming_links.isrc IS
    'International Standard Recording Code - can be used for cross-service matching';

-- Verification (run after migration)
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name IN ('release_streaming_links', 'recording_release_streaming_links');


