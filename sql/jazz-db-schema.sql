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
	musicbrainz_id VARCHAR(36) UNIQUE,
	wikipedia_url VARCHAR(500),
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
    wikipedia_url VARCHAR(500),
    musicbrainz_id VARCHAR(255),
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
    musicbrainz_id VARCHAR(255) UNIQUE,
    spotify_track_id VARCHAR(100),
    album_art_small VARCHAR(500),
    album_art_medium VARCHAR(500),
    album_art_large VARCHAR(500)
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
-- Migration: Add Images Support
-- Description: Adds images table and artist_images junction table
-- ============================================================================

-- Images table
CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url VARCHAR(1000) NOT NULL,
    source VARCHAR(100) NOT NULL, -- 'wikipedia', 'discogs', 'musicbrainz', etc.
    source_identifier VARCHAR(255), -- ID from external source (e.g., Discogs artist ID)
    license_type VARCHAR(100), -- 'cc-by-sa', 'cc-by', 'public-domain', 'all-rights-reserved', etc.
    license_url VARCHAR(500), -- URL to license details
    attribution TEXT, -- Required attribution text
    width INTEGER, -- Original image width in pixels
    height INTEGER, -- Original image height in pixels
    thumbnail_url VARCHAR(1000), -- Smaller version if available
    source_page_url VARCHAR(1000), -- URL to the page where image was found
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_identifier, url) -- Prevent duplicate images from same source
);

-- Artist images junction table (many-to-many)
CREATE TABLE IF NOT EXISTS artist_images (
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false, -- Flag one image as the primary/profile image
    display_order INTEGER DEFAULT 0, -- Order for displaying multiple images
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (performer_id, image_id)
);



CREATE TABLE IF NOT EXISTS solo_transcriptions (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    song_id uuid NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    recording_id uuid NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    youtube_url character varying(500),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100),
    updated_by character varying(100)
);




-- Add comments for documentation
COMMENT ON COLUMN recordings.spotify_track_id IS 'Spotify track ID extracted from spotify_url';
COMMENT ON COLUMN recordings.album_art_small IS 'Small album artwork (64x64) from Spotify';
COMMENT ON COLUMN recordings.album_art_medium IS 'Medium album artwork (300x300) from Spotify';
COMMENT ON COLUMN recordings.album_art_large IS 'Large album artwork (640x640) from Spotify';
-- Triggers -------------------------------------------------------



CREATE TABLE IF NOT EXISTS repertoires (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                
CREATE INDEX IF NOT EXISTS idx_repertoires_name 
	ON repertoires(name)
	
CREATE INDEX idx_repertoires_user_id ON repertoires(user_id)
	
COMMENT ON COLUMN repertoires.user_id IS 'Owner of this repertoire. NULL for system/public repertoires.'
	
CREATE TABLE IF NOT EXISTS repertoire_songs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repertoire_id UUID NOT NULL,
    song_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_repertoire
        FOREIGN KEY (repertoire_id)
        REFERENCES repertoires(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_song
        FOREIGN KEY (song_id)
        REFERENCES songs(id)
        ON DELETE CASCADE,
    CONSTRAINT unique_repertoire_song
        UNIQUE (repertoire_id, song_id)
)

CREATE INDEX IF NOT EXISTS idx_repertoire_songs_repertoire_id 
ON repertoire_songs(repertoire_id)

CREATE INDEX IF NOT EXISTS idx_repertoire_songs_song_id 
ON repertoire_songs(song_id)

- Create the authority recommendations table
CREATE TABLE IF NOT EXISTS song_authority_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    source VARCHAR(100) NOT NULL,  -- e.g., 'jazzstandards.com', 'ted_gioia', 'allmusic'
    recommendation_text TEXT,  -- The actual text from the source
    source_url TEXT NOT NULL,  -- URL where we found this recommendation
    artist_name VARCHAR(255),  -- Artist mentioned in the recommendation
    album_title VARCHAR(255),  -- Album mentioned in the recommendation
    recording_year INTEGER,  -- Year if mentioned
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_authority_recs_song_id ON song_authority_recommendations(song_id);
CREATE INDEX idx_authority_recs_recording_id ON song_authority_recommendations(recording_id);
CREATE INDEX idx_authority_recs_source ON song_authority_recommendations(source);
CREATE INDEX idx_authority_recs_captured_at ON song_authority_recommendations(captured_at);

-- Add comments for documentation
COMMENT ON TABLE song_authority_recommendations IS 'Expert recommendations for recordings of jazz standards from authoritative sources';
COMMENT ON COLUMN song_authority_recommendations.song_id IS 'The song this recommendation is for';
COMMENT ON COLUMN song_authority_recommendations.recording_id IS 'The recording in our database (NULL if not yet matched)';
COMMENT ON COLUMN song_authority_recommendations.source IS 'Source of authority (e.g., jazzstandards.com, ted_gioia)';
COMMENT ON COLUMN song_authority_recommendations.recommendation_text IS 'Raw recommendation text from the source';
COMMENT ON COLUMN song_authority_recommendations.source_url IS 'URL where the recommendation was found';
COMMENT ON COLUMN song_authority_recommendations.artist_name IS 'Artist name mentioned in the recommendation';
COMMENT ON COLUMN song_authority_recommendations.album_title IS 'Album title mentioned in the recommendation';
COMMENT ON COLUMN song_authority_recommendations.recording_year IS 'Recording year if mentioned';
COMMENT ON COLUMN song_authority_recommendations.captured_at IS 'When we fetched this recommendation from the source';

-- Create a view for songs with their authority recommendations count
CREATE OR REPLACE VIEW songs_with_authority_recs AS
SELECT
    s.id as song_id,
    s.title,
    COUNT(sar.id) as recommendation_count,
    COUNT(DISTINCT sar.source) as source_count,
    array_agg(DISTINCT sar.source) FILTER (WHERE sar.source IS NOT NULL) as sources
FROM songs s
LEFT JOIN song_authority_recommendations sar ON s.id = sar.song_id
GROUP BY s.id, s.title;

COMMENT ON VIEW songs_with_authority_recs IS 'Songs with count of authority recommendations from various sources';


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
-- USERS TABLE
-- ============================================================================
-- Core users table supporting multiple authentication methods
-- Users can sign up with email/password, Google, or Apple
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT false,
    password_hash VARCHAR(255), -- NULL for OAuth-only users
    display_name VARCHAR(255),
    profile_image_url VARCHAR(500),
    
    -- OAuth provider info
    google_id VARCHAR(255) UNIQUE,
    apple_id VARCHAR(255) UNIQUE,
    
    -- Account status
    is_active BOOLEAN DEFAULT true,
    account_locked BOOLEAN DEFAULT false,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    -- User must have at least one authentication method
    CONSTRAINT check_auth_method CHECK (
        password_hash IS NOT NULL OR 
        google_id IS NOT NULL OR 
        apple_id IS NOT NULL
    )
);

-- ============================================================================
-- PASSWORD RESET TOKENS
-- ============================================================================
-- Tokens for password reset flow
-- Each token is single-use and expires after a set period
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- EMAIL VERIFICATION TOKENS
-- ============================================================================
-- Tokens for email verification flow
-- Users must verify their email to enable certain features
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- REFRESH TOKENS
-- ============================================================================
-- Long-lived tokens for JWT token rotation
-- Allows secure automatic re-authentication
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    device_info JSONB -- Store device/app info for security auditing
);

-- ============================================================================
-- INDEXES
-- ============================================================================
-- Indexes for efficient queries on authentication tables

-- Users table indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_apple_id ON users(apple_id);

-- Password reset tokens indexes
CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

-- Email verification tokens indexes
CREATE INDEX idx_email_verification_tokens_token ON email_verification_tokens(token);
CREATE INDEX idx_email_verification_tokens_user_id ON email_verification_tokens(user_id);

-- Refresh tokens indexes
CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================
-- Trigger to automatically update updated_at timestamp on users table
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS
-- ============================================================================
-- Add documentation comments to tables and key columns
COMMENT ON TABLE users IS 'Core users table for authentication supporting email/password, Google OAuth, and Apple Sign In';
COMMENT ON TABLE password_reset_tokens IS 'Single-use tokens for password reset flow';
COMMENT ON TABLE email_verification_tokens IS 'Tokens for email verification flow';
COMMENT ON TABLE refresh_tokens IS 'Long-lived tokens for JWT token rotation';

COMMENT ON COLUMN users.email IS 'User email address - must be unique';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password - NULL for OAuth-only users';
COMMENT ON COLUMN users.google_id IS 'Google OAuth user identifier - unique';
COMMENT ON COLUMN users.apple_id IS 'Apple Sign In user identifier - unique';
COMMENT ON COLUMN users.failed_login_attempts IS 'Counter for rate limiting - resets on successful login';
COMMENT ON COLUMN users.account_locked IS 'True if account locked due to excessive failed login attempts';




-- ============================================================================
-- Migration: Add Content Error Reporting
-- Run this on your Supabase database
-- ============================================================================

-- Create content_reports table
CREATE TABLE content_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Entity identification (polymorphic relationship)
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('song', 'performer', 'recording')),
    entity_id UUID NOT NULL,
    entity_name VARCHAR(255) NOT NULL,
    
    -- Report classification
    report_category VARCHAR(50) NOT NULL DEFAULT 'link_issue', 
    -- Categories: 'link_issue', 'wrong_entity_linked', 'incorrect_info', 'missing_info', 'duplicate', 'other'
    
    -- External reference details
    external_source VARCHAR(100) NOT NULL, 
    external_url VARCHAR(1000) NOT NULL,
    
    -- User's explanation
    explanation TEXT NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' NOT NULL 
        CHECK (status IN ('pending', 'reviewing', 'resolved', 'dismissed', 'duplicate')),
    priority VARCHAR(20) DEFAULT 'normal' 
        CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    
    -- Resolution details
    resolution_notes TEXT,
    resolution_action VARCHAR(100),
    
    -- Reporter metadata (anonymous)
    reporter_ip VARCHAR(45),
    reporter_user_agent TEXT,
    reporter_platform VARCHAR(50),
    reporter_app_version VARCHAR(50),
    
    -- Admin handling
    reviewed_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes
CREATE INDEX idx_content_reports_entity ON content_reports(entity_type, entity_id);
CREATE INDEX idx_content_reports_entity_id ON content_reports(entity_id);
CREATE INDEX idx_content_reports_status ON content_reports(status) WHERE status IN ('pending', 'reviewing');
CREATE INDEX idx_content_reports_created_at ON content_reports(created_at DESC);
CREATE INDEX idx_content_reports_external_source ON content_reports(external_source);

-- Add trigger for updated_at
CREATE TRIGGER update_content_reports_updated_at 
    BEFORE UPDATE ON content_reports
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE content_reports IS 'User-submitted reports of issues with external links and content';
COMMENT ON COLUMN content_reports.entity_type IS 'Type of entity: song, performer, or recording';
COMMENT ON COLUMN content_reports.report_category IS 'Type of issue: link_issue (broken/404), wrong_entity_linked (link points to different entity or entity does not exist on this source), incorrect_info, missing_info, duplicate, other';
COMMENT ON COLUMN content_reports.external_source IS 'External service: wikipedia, musicbrainz, spotify, youtube, apple_music, jazzstandards';
COMMENT ON COLUMN content_reports.status IS 'Current status: pending, reviewing, resolved, dismissed, duplicate';
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
CREATE INDEX idx_performers_wikipedia_url ON performers(wikipedia_url) WHERE wikipedia_url IS NOT NULL;
CREATE INDEX idx_performers_musicbrainz_id ON performers(musicbrainz_id) WHERE musicbrainz_id IS NOT NULL;

-- Recording indexes
CREATE INDEX idx_recordings_song_id ON recordings(song_id);
CREATE INDEX idx_recordings_year ON recordings(recording_year);
CREATE INDEX idx_recordings_is_canonical ON recordings(is_canonical);
CREATE INDEX idx_recordings_album_title ON recordings(album_title);
CREATE INDEX idx_recordings_spotify_track_id ON recordings(spotify_track_id);

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

-- Add index on external_links for performers (if it doesn't exist)
-- This will help us store Discogs IDs, Wikipedia URLs, etc.
CREATE INDEX IF NOT EXISTS idx_performers_external_links ON performers USING gin(external_links);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_images_source ON images(source);
CREATE INDEX IF NOT EXISTS idx_images_source_identifier ON images(source_identifier);
CREATE INDEX IF NOT EXISTS idx_artist_images_performer ON artist_images(performer_id);
CREATE INDEX IF NOT EXISTS idx_artist_images_image ON artist_images(image_id);
CREATE INDEX IF NOT EXISTS idx_artist_images_primary ON artist_images(is_primary) WHERE is_primary = true;

CREATE UNIQUE INDEX solo_transcriptions_pkey ON solo_transcriptions(id uuid_ops);
CREATE INDEX idx_solo_transcriptions_song_id ON solo_transcriptions(song_id uuid_ops);
CREATE INDEX idx_solo_transcriptions_recording_id ON solo_transcriptions(recording_id uuid_ops);


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

-- Add updated_at trigger for images
CREATE OR REPLACE FUNCTION update_images_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_images_updated_at
    BEFORE UPDATE ON images
    FOR EACH ROW
    EXECUTE FUNCTION update_images_updated_at();

CREATE TRIGGER update_solo_transcriptions_updated_at
  BEFORE UPDATE ON public.solo_transcriptions
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();


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
COMMENT ON COLUMN performers.wikipedia_url IS 'Direct link to Wikipedia article for this performer';
COMMENT ON COLUMN performers.musicbrainz_id IS 'MusicBrainz artist ID (UUID format)';
COMMENT ON TABLE instruments IS 'Reference table for musical instruments';
COMMENT ON TABLE recording_performers IS 'Junction table linking performers to recordings with their instrument roles';
COMMENT ON TABLE videos IS 'YouTube videos linked to songs or recordings';
COMMENT ON COLUMN recordings.is_canonical IS 'Flag indicating this is the definitive/recommended recording of the song';
COMMENT ON COLUMN songs.external_references IS 'JSON object containing Wikipedia URLs, book references, and other external links';
-- Comments for documentation
COMMENT ON TABLE images IS 'Stores external image URLs with licensing and attribution information';
COMMENT ON TABLE artist_images IS 'Many-to-many relationship between performers and images';
COMMENT ON COLUMN images.license_type IS 'License type: cc-by-sa, cc-by, cc0, public-domain, all-rights-reserved, etc.';
COMMENT ON COLUMN images.source IS 'Source of the image: wikipedia, discogs, musicbrainz, manual, etc.';
COMMENT ON COLUMN images.source_identifier IS 'External ID from the source system (e.g., Discogs artist ID)';
COMMENT ON COLUMN artist_images.is_primary IS 'Marks the primary/profile image for an artist';
COMMENT ON COLUMN artist_images.display_order IS 'Order for displaying images in carousel (lower numbers first)';
COMMENT ON TABLE solo_transcriptions IS 'Specific solo transcriptions for a song and recording';


