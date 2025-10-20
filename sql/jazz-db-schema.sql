-- Jazz Reference Application - PostgreSQL Database Schema

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Songs table
CREATE TABLE songs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    composer VARCHAR(500),
    song_reference TEXT, -- written background information about the song
    structure TEXT, -- Chord progressions, form description
    external_references JSONB, -- Store Wikipedia links, book references, etc.
	musicbrainz_id VARCHAR(36) UNIQUE;
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Performers table
CREATE TABLE performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    biography TEXT,
    birth_date DATE,
    death_date DATE,
    external_links JSONB, -- Store social media, official websites, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Instruments table (lookup/reference table)
CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50), -- e.g., 'woodwind', 'brass', 'percussion', 'string', 'keyboard'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performer instruments (many-to-many)
CREATE TABLE performer_instruments (
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false, -- Flag primary instrument
    proficiency_level VARCHAR(50), -- e.g., 'expert', 'proficient', 'occasional'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (performer_id, instrument_id)
);

-- Recordings table
CREATE TABLE recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    album_title VARCHAR(255),
    recording_date DATE,
    recording_year INTEGER,
    label VARCHAR(255),
    spotify_url VARCHAR(500),
    youtube_url VARCHAR(500),
    apple_music_url VARCHAR(500),
    is_canonical BOOLEAN DEFAULT false,
    notes TEXT, -- Additional context about the recording
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    musicbrainz_id VARCHAR(255) UNIQUE
);

-- Recording performers (junction table with instrument role)
CREATE TABLE recording_performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID REFERENCES instruments(id) ON DELETE SET NULL,
    role VARCHAR(100), -- e.g., 'leader', 'sideman', 'guest'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recording_id, performer_id, instrument_id)
);

-- Videos table
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID REFERENCES songs(id) ON DELETE SET NULL,
    recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    youtube_url VARCHAR(500) NOT NULL,
    title VARCHAR(255),
    description TEXT,
    video_type VARCHAR(50) NOT NULL, -- 'performance', 'transcription', 'educational'
    duration_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT video_must_link_to_song_or_recording CHECK (
        (song_id IS NOT NULL) OR (recording_id IS NOT NULL)
    )
);

-- Video performers (optional - for videos that feature specific performers)
CREATE TABLE video_performers (
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (video_id, performer_id)
);

-- ============================================================================
-- ADMIN & VERSIONING TABLES
-- ============================================================================

-- Admin users table
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'editor', -- 'admin', 'editor', 'moderator'
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit log for tracking changes
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Song indexes
CREATE INDEX idx_songs_title ON songs(title);
-- CREATE INDEX idx_songs_title_trgm ON songs USING gin(title gin_trgm_ops);
CREATE INDEX idx_songs_composer ON songs(composer);
CREATE INDEX idx_songs_musicbrainz_id ON songs(musicbrainz_id);


-- Performer indexes
CREATE INDEX idx_performers_name ON performers(name);
-- CREATE INDEX idx_performers_name_trgm ON performers USING gin(name gin_trgm_ops);

-- Recording indexes
CREATE INDEX idx_recordings_song_id ON recordings(song_id);
CREATE INDEX idx_recordings_year ON recordings(recording_year);
CREATE INDEX idx_recordings_is_canonical ON recordings(is_canonical);
CREATE INDEX idx_recordings_album_title ON recordings(album_title);

-- Recording performer indexes
CREATE INDEX idx_recording_performers_recording_id ON recording_performers(recording_id);
CREATE INDEX idx_recording_performers_performer_id ON recording_performers(performer_id);
CREATE INDEX idx_recording_performers_instrument_id ON recording_performers(instrument_id);

-- Video indexes
CREATE INDEX idx_videos_song_id ON videos(song_id);
CREATE INDEX idx_videos_recording_id ON videos(recording_id);
CREATE INDEX idx_videos_type ON videos(video_type);

-- Instrument indexes
CREATE INDEX idx_instruments_name ON instruments(name);
CREATE INDEX idx_instruments_category ON instruments(category);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic updated_at updates
CREATE TRIGGER update_songs_updated_at BEFORE UPDATE ON songs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_performers_updated_at BEFORE UPDATE ON performers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_recordings_updated_at BEFORE UPDATE ON recordings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert common jazz instruments
INSERT INTO instruments (name, category) VALUES
    ('Trumpet', 'brass'),
    ('Trombone', 'brass'),
    ('Saxophone', 'woodwind'),
    ('Alto Saxophone', 'woodwind'),
    ('Tenor Saxophone', 'woodwind'),
    ('Baritone Saxophone', 'woodwind'),
    ('Soprano Saxophone', 'woodwind'),
    ('Clarinet', 'woodwind'),
    ('Flute', 'woodwind'),
    ('Piano', 'keyboard'),
    ('Organ', 'keyboard'),
    ('Electric Piano', 'keyboard'),
    ('Bass', 'string'),
    ('Upright Bass', 'string'),
    ('Electric Bass', 'string'),
    ('Guitar', 'string'),
    ('Electric Guitar', 'string'),
    ('Acoustic Guitar', 'string'),
    ('Drums', 'percussion'),
    ('Vibraphone', 'percussion'),
    ('Percussion', 'percussion'),
    ('Vocals', 'voice')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for songs with canonical recording information
CREATE OR REPLACE VIEW songs_with_canonical_recordings AS
SELECT
    s.id as song_id,
    s.title,
    s.composer,
    r.id as canonical_recording_id,
    r.album_title,
    r.recording_year,
    r.spotify_url,
    r.youtube_url
FROM songs s
LEFT JOIN recordings r ON s.id = r.song_id AND r.is_canonical = true;

-- View for performer discography
CREATE OR REPLACE VIEW performer_discography AS
SELECT
    p.id as performer_id,
    p.name as performer_name,
    s.id as song_id,
    s.title as song_title,
    r.id as recording_id,
    r.album_title,
    r.recording_year,
    i.name as instrument,
    rp.role
FROM performers p
JOIN recording_performers rp ON p.id = rp.performer_id
JOIN recordings r ON rp.recording_id = r.id
JOIN songs s ON r.song_id = s.id
LEFT JOIN instruments i ON rp.instrument_id = i.id
ORDER BY p.name, r.recording_year DESC;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE songs IS 'Core table storing jazz standard songs and compositions';
COMMENT ON COLUMN songs.musicbrainz_id IS 'MusicBrainz Work ID for this song/composition';
COMMENT ON TABLE recordings IS 'Specific recordings of songs with album and streaming information';
COMMENT ON TABLE performers IS 'Jazz musicians and vocalists';
COMMENT ON TABLE instruments IS 'Reference table for musical instruments';
COMMENT ON TABLE recording_performers IS 'Junction table linking performers to recordings with their instrument roles';
COMMENT ON TABLE videos IS 'YouTube videos linked to songs or recordings';
COMMENT ON COLUMN recordings.is_canonical IS 'Flag indicating this is the definitive/recommended recording of the song';
COMMENT ON COLUMN songs.external_references IS 'JSON object containing Wikipedia URLs, book references, and other external links';
