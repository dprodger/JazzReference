-- Jazz Reference Application - PostgreSQL Database Schema

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable unaccent extension for accent-insensitive text matching
-- (e.g., "Mel Tormé" matches "Mel Torme")
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Songs table
CREATE TABLE songs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    composer VARCHAR(500),
    composed_year INTEGER, -- Year the song was originally composed
    composed_key VARCHAR(10), -- Original key (e.g., C, Bb, F#m)
    song_reference TEXT, -- written background information about the song
    structure TEXT, -- Chord progressions, form description
    external_references JSONB, -- Store Wikipedia links, book references, etc.
	musicbrainz_id VARCHAR(36) UNIQUE,
	second_mb_id VARCHAR(36), -- Secondary MusicBrainz work ID for songs with multiple MB works
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
    sort_name VARCHAR(255),           -- MusicBrainz sort name (e.g., "Davis, Miles")
    artist_type VARCHAR(50),          -- MusicBrainz type: Person, Group, Orchestra, etc.
    disambiguation VARCHAR(500),      -- MusicBrainz disambiguation text
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
    recording_date_source VARCHAR(50),      -- 'mb_performer_relation', 'mb_first_release', 'earliest_release', 'manual'
    recording_date_precision VARCHAR(10),   -- 'day', 'month', 'year'
    mb_first_release_date VARCHAR(10),      -- MusicBrainz first-release-date (YYYY, YYYY-MM, or YYYY-MM-DD)
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
    source_mb_work_id VARCHAR(36), -- MusicBrainz work ID this recording was imported from
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
	created_by VARCHAR(100) NOT NULL;
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
    recording_id uuid REFERENCES recordings(id),
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
COMMENT ON COLUMN recordings.recording_date IS 'Best known recording session date. Source tracked in recording_date_source.';
COMMENT ON COLUMN recordings.recording_year IS 'Recording year - may be more reliable than full date when precision is limited.';
COMMENT ON COLUMN recordings.recording_date_source IS 'Source of recording_date: mb_performer_relation, mb_first_release, earliest_release, manual';
COMMENT ON COLUMN recordings.recording_date_precision IS 'Precision of recording_date: day (YYYY-MM-DD), month (YYYY-MM), year (YYYY only)';
COMMENT ON COLUMN recordings.mb_first_release_date IS 'MusicBrainz first-release-date cached. Upper bound for recording date.';
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


-- Add iTunes ID columns
ALTER TABLE song_authority_recommendations 
ADD COLUMN itunes_album_id BIGINT,
ADD COLUMN itunes_track_id BIGINT;

-- Add indexes for iTunes ID lookups
CREATE INDEX idx_song_authority_recs_itunes_album 
ON song_authority_recommendations(itunes_album_id) 
WHERE itunes_album_id IS NOT NULL;

CREATE INDEX idx_song_authority_recs_itunes_track 
ON song_authority_recommendations(itunes_track_id) 
WHERE itunes_track_id IS NOT NULL;

-- Add comment
COMMENT ON COLUMN song_authority_recommendations.itunes_album_id IS 
'iTunes/Apple Music album ID extracted from recommendation links';

COMMENT ON COLUMN song_authority_recommendations.itunes_track_id IS 
'iTunes/Apple Music track ID extracted from recommendation links (optional)';


-- ============================================================================
-- Migration: Add Releases Table
-- Description: Adds support for MusicBrainz Release entities, capturing different
--              physical/digital releases of the same recording (original albums,
--              reissues, compilations, remasters, etc.)
-- ============================================================================

-- ============================================================================
-- LOOKUP TABLES
-- ============================================================================

-- Release status lookup (mirrors MusicBrainz release status)
CREATE TABLE IF NOT EXISTS release_statuses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed release status values from MusicBrainz
INSERT INTO release_statuses (name, description) VALUES
    ('official', 'Any release officially sanctioned by the artist and/or their record company'),
    ('promotional', 'A give-away release or a release intended to promote an upcoming official release'),
    ('bootleg', 'An unofficial/underground release that was not sanctioned by the artist or record company'),
    ('pseudo-release', 'A pseudo-release (e.g., a duplicate release in another language)')
ON CONFLICT (name) DO NOTHING;


-- Release format lookup (medium format from MusicBrainz)
CREATE TABLE IF NOT EXISTS release_formats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50), -- 'physical', 'digital', 'other'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed common release formats from MusicBrainz
INSERT INTO release_formats (name, category, description) VALUES
    ('CD', 'physical', 'Compact Disc'),
    ('Vinyl', 'physical', 'Vinyl record (any size)'),
    ('12" Vinyl', 'physical', '12-inch vinyl record'),
    ('10" Vinyl', 'physical', '10-inch vinyl record'),
    ('7" Vinyl', 'physical', '7-inch vinyl single'),
    ('Cassette', 'physical', 'Cassette tape'),
    ('Digital Media', 'digital', 'Digital download or streaming'),
    ('SACD', 'physical', 'Super Audio CD'),
    ('DVD', 'physical', 'DVD (audio or video)'),
    ('DVD-Audio', 'physical', 'DVD-Audio'),
    ('Blu-ray', 'physical', 'Blu-ray disc'),
    ('HD-DVD', 'physical', 'HD-DVD'),
    ('Enhanced CD', 'physical', 'CD with additional data content'),
    ('HDCD', 'physical', 'High Definition Compatible Digital'),
    ('DualDisc', 'physical', 'Dual-sided disc with CD and DVD'),
    ('Hybrid SACD', 'physical', 'SACD with CD-compatible layer'),
    ('USB Flash Drive', 'physical', 'USB storage device'),
    ('Other', 'other', 'Other format not listed')
ON CONFLICT (name) DO NOTHING;


-- Release packaging lookup (from MusicBrainz)
CREATE TABLE IF NOT EXISTS release_packaging (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed common packaging types from MusicBrainz
INSERT INTO release_packaging (name, description) VALUES
    ('Jewel Case', 'Standard CD jewel case'),
    ('Slim Jewel Case', 'Slim-line jewel case'),
    ('Digipak', 'Cardboard/paper folding case'),
    ('Cardboard/Paper Sleeve', 'Simple paper or cardboard sleeve'),
    ('Keep Case', 'Standard DVD/Blu-ray case'),
    ('None', 'No packaging (digital releases)'),
    ('Gatefold Cover', 'Folding cover, typically for vinyl'),
    ('Box', 'Box set packaging'),
    ('Book', 'Book-style packaging'),
    ('Plastic Sleeve', 'Plastic protective sleeve'),
    ('Digibook', 'Book-style digipak'),
    ('Super Jewel Box', 'Oversized jewel case'),
    ('Snap Case', 'Plastic case with snap closure'),
    ('Slidepak', 'Sliding cardboard case'),
    ('Other', 'Other packaging type')
ON CONFLICT (name) DO NOTHING;


-- ============================================================================
-- MAIN RELEASES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- MusicBrainz identification
    musicbrainz_release_id VARCHAR(36) UNIQUE,  -- MusicBrainz Release MBID
    musicbrainz_release_group_id VARCHAR(36),   -- Release Group MBID (groups editions together)
    
    -- Release information
    title VARCHAR(500) NOT NULL,
    artist_credit VARCHAR(500),                  -- Artist as credited on this release
    disambiguation VARCHAR(500),                 -- To differentiate similar releases
    
    -- Release event information
    release_date DATE,
    release_year INTEGER,                        -- For partial dates (year only)
    country VARCHAR(2),                          -- ISO 3166-1 alpha-2 country code
    
    -- Label and catalog information
    label VARCHAR(255),
    catalog_number VARCHAR(100),
    barcode VARCHAR(50),
    
    -- Format and packaging
    format_id INTEGER REFERENCES release_formats(id),
    packaging_id INTEGER REFERENCES release_packaging(id),
    status_id INTEGER REFERENCES release_statuses(id),
    
    -- Additional metadata
    language VARCHAR(10),                        -- ISO 639-3 language code
    script VARCHAR(10),                          -- ISO 15924 script code
    total_tracks INTEGER,
    total_discs INTEGER DEFAULT 1,
    
    -- Cover art (different releases may have different covers)
    cover_art_url VARCHAR(500),
    cover_art_small VARCHAR(500),
    cover_art_medium VARCHAR(500),
    cover_art_large VARCHAR(500),
    
    -- External links
    spotify_album_id VARCHAR(50),
    spotify_album_url VARCHAR(500),
    apple_music_url VARCHAR(500),
    amazon_url VARCHAR(500),
    discogs_url VARCHAR(500),
    
    -- Quality/annotation
    data_quality VARCHAR(50),                    -- MusicBrainz data quality rating
    annotation TEXT,                             -- Notes about this release
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);


-- ============================================================================
-- JUNCTION TABLE: RECORDING <-> RELEASE (Many-to-Many)
-- ============================================================================

-- A recording can appear on multiple releases (original album, greatest hits, etc.)
-- A release contains multiple recordings (tracks)
CREATE TABLE IF NOT EXISTS recording_releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    
    -- Track position on the release
    disc_number INTEGER DEFAULT 1,
    track_number INTEGER,
    track_position VARCHAR(20),                  -- For complex numbering like "A1", "B2"
    
    -- Track-specific information (may differ from recording)
    track_title VARCHAR(500),                    -- Title as shown on this release (may differ)
    track_artist_credit VARCHAR(500),            -- Artist credit on this specific track
    track_length_ms INTEGER,                     -- Duration in milliseconds
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate track entries
    UNIQUE (recording_id, release_id, disc_number, track_number)
);


-- ============================================================================
-- RELEASE LABELS (Multiple labels can be associated with a release)
-- ============================================================================

CREATE TABLE IF NOT EXISTS release_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    label_name VARCHAR(255) NOT NULL,
    catalog_number VARCHAR(100),
    musicbrainz_label_id VARCHAR(36),            -- MusicBrainz Label MBID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (release_id, label_name, catalog_number)
);


-- ============================================================================
-- RELEASE EVENTS (A release can have multiple release events in different countries)
-- ============================================================================

CREATE TABLE IF NOT EXISTS release_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    country VARCHAR(2),                          -- ISO 3166-1 alpha-2
    release_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (release_id, country, release_date)
);


-- ============================================================================
-- INDEXES
-- ============================================================================

-- Releases table indexes
CREATE INDEX IF NOT EXISTS idx_releases_musicbrainz_release_id 
    ON releases(musicbrainz_release_id);
CREATE INDEX IF NOT EXISTS idx_releases_musicbrainz_release_group_id 
    ON releases(musicbrainz_release_group_id);
CREATE INDEX IF NOT EXISTS idx_releases_title 
    ON releases(title);
CREATE INDEX IF NOT EXISTS idx_releases_artist_credit 
    ON releases(artist_credit);
CREATE INDEX IF NOT EXISTS idx_releases_release_date 
    ON releases(release_date);
CREATE INDEX IF NOT EXISTS idx_releases_release_year 
    ON releases(release_year);
CREATE INDEX IF NOT EXISTS idx_releases_label 
    ON releases(label);
CREATE INDEX IF NOT EXISTS idx_releases_barcode 
    ON releases(barcode);
CREATE INDEX IF NOT EXISTS idx_releases_spotify_album_id 
    ON releases(spotify_album_id);

-- Recording-releases junction table indexes
CREATE INDEX IF NOT EXISTS idx_recording_releases_recording_id 
    ON recording_releases(recording_id);
CREATE INDEX IF NOT EXISTS idx_recording_releases_release_id 
    ON recording_releases(release_id);
CREATE INDEX IF NOT EXISTS idx_recording_releases_disc_track 
    ON recording_releases(release_id, disc_number, track_number);

-- Release labels indexes
CREATE INDEX IF NOT EXISTS idx_release_labels_release_id 
    ON release_labels(release_id);
CREATE INDEX IF NOT EXISTS idx_release_labels_label_name 
    ON release_labels(label_name);

-- Release events indexes
CREATE INDEX IF NOT EXISTS idx_release_events_release_id 
    ON release_events(release_id);
CREATE INDEX IF NOT EXISTS idx_release_events_country 
    ON release_events(country);


-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE releases IS 
    'MusicBrainz Release entities - specific product releases (albums, CDs, digital releases). A recording can appear on multiple releases.';

COMMENT ON TABLE recording_releases IS 
    'Junction table linking recordings to releases. Captures track position and any release-specific track information.';

COMMENT ON TABLE release_labels IS 
    'Labels associated with a release. A release can have multiple labels each with their own catalog number.';

COMMENT ON TABLE release_events IS 
    'Release events for different countries. A release can have different release dates in different regions.';

COMMENT ON TABLE release_statuses IS 
    'Lookup table for release status (official, promotional, bootleg, pseudo-release).';

COMMENT ON TABLE release_formats IS 
    'Lookup table for medium formats (CD, vinyl, digital, etc.).';

COMMENT ON TABLE release_packaging IS 
    'Lookup table for physical packaging types (jewel case, digipak, etc.).';

COMMENT ON COLUMN releases.musicbrainz_release_id IS 
    'MusicBrainz Release MBID - unique identifier for this specific release.';

COMMENT ON COLUMN releases.musicbrainz_release_group_id IS 
    'MusicBrainz Release Group MBID - groups together different editions of the same album.';

COMMENT ON COLUMN releases.disambiguation IS 
    'Text to help distinguish this release from similar ones (e.g., "Deluxe Edition", "Japanese pressing").';

COMMENT ON COLUMN recording_releases.track_title IS 
    'Track title as shown on this specific release, which may differ from the canonical recording title.';


-- ============================================================================
-- VIEWS
-- ============================================================================

-- View to show recordings with their releases
CREATE OR REPLACE VIEW recordings_with_releases AS
SELECT
    r.id as recording_id,
    r.album_title as recording_album_title,
    r.musicbrainz_id as recording_musicbrainz_id,
    s.id as song_id,
    s.title as song_title,
    rel.id as release_id,
    rel.title as release_title,
    rel.musicbrainz_release_id,
    rel.release_date,
    rel.release_year,
    rel.label,
    rel.country,
    rf.name as format,
    rs.name as status,
    rr.disc_number,
    rr.track_number
FROM recordings r
JOIN songs s ON r.song_id = s.id
LEFT JOIN recording_releases rr ON r.id = rr.recording_id
LEFT JOIN releases rel ON rr.release_id = rel.id
LEFT JOIN release_formats rf ON rel.format_id = rf.id
LEFT JOIN release_statuses rs ON rel.status_id = rs.id
ORDER BY s.title, rel.release_date;


-- View to show release details with track listing
CREATE OR REPLACE VIEW release_tracklist AS
SELECT
    rel.id as release_id,
    rel.title as release_title,
    rel.artist_credit,
    rel.release_date,
    rel.label,
    rf.name as format,
    rr.disc_number,
    rr.track_number,
    COALESCE(rr.track_title, r.album_title) as track_title,
    r.id as recording_id,
    r.musicbrainz_id as recording_musicbrainz_id,
    s.title as song_title,
    s.composer
FROM releases rel
LEFT JOIN recording_releases rr ON rel.id = rr.release_id
LEFT JOIN recordings r ON rr.recording_id = r.id
LEFT JOIN songs s ON r.song_id = s.id
LEFT JOIN release_formats rf ON rel.format_id = rf.id
ORDER BY rel.title, rr.disc_number, rr.track_number;


-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger to update updated_at timestamp on releases
CREATE OR REPLACE FUNCTION update_releases_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_releases_updated_at ON releases;
CREATE TRIGGER trigger_releases_updated_at
    BEFORE UPDATE ON releases
    FOR EACH ROW
    EXECUTE FUNCTION update_releases_updated_at();


-- ============================================================================
-- VERIFICATION QUERY (run after migration to verify success)
-- ============================================================================

-- Uncomment and run to verify:
-- SELECT 
--     (SELECT COUNT(*) FROM release_statuses) as status_count,
--     (SELECT COUNT(*) FROM release_formats) as format_count,
--     (SELECT COUNT(*) FROM release_packaging) as packaging_count,
--     (SELECT COUNT(*) FROM information_schema.tables 
--      WHERE table_name IN ('releases', 'recording_releases', 'release_labels', 'release_events')) as table_count;
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
CREATE INDEX idx_recordings_recording_date_source ON recordings(recording_date_source) WHERE recording_date_source IS NOT NULL;
CREATE INDEX idx_recordings_mb_first_release_date ON recordings(mb_first_release_date) WHERE mb_first_release_date IS NOT NULL;

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


-- ============================================================================
-- Migration: Add Releases Tables
-- Description: Adds support for MusicBrainz Release entities
-- Run this migration BEFORE using the updated import_mb_releases.py script
-- ============================================================================

-- ============================================================================
-- LOOKUP TABLES
-- ============================================================================

-- Release status lookup (mirrors MusicBrainz release status)
CREATE TABLE IF NOT EXISTS release_statuses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed release status values from MusicBrainz
INSERT INTO release_statuses (name, description) VALUES
    ('official', 'Any release officially sanctioned by the artist and/or their record company'),
    ('promotional', 'A give-away release or a release intended to promote an upcoming official release'),
    ('bootleg', 'An unofficial/underground release that was not sanctioned by the artist or record company'),
    ('pseudo-release', 'A pseudo-release (e.g., a duplicate release in another language)')
ON CONFLICT (name) DO NOTHING;


-- Release format lookup (medium format from MusicBrainz)
CREATE TABLE IF NOT EXISTS release_formats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed common release formats from MusicBrainz
INSERT INTO release_formats (name, category, description) VALUES
    ('CD', 'physical', 'Compact Disc'),
    ('Vinyl', 'physical', 'Vinyl record (any size)'),
    ('12" Vinyl', 'physical', '12-inch vinyl record'),
    ('10" Vinyl', 'physical', '10-inch vinyl record'),
    ('7" Vinyl', 'physical', '7-inch vinyl single'),
    ('Cassette', 'physical', 'Cassette tape'),
    ('Digital Media', 'digital', 'Digital download or streaming'),
    ('SACD', 'physical', 'Super Audio CD'),
    ('DVD', 'physical', 'DVD (audio or video)'),
    ('DVD-Audio', 'physical', 'DVD-Audio'),
    ('Blu-ray', 'physical', 'Blu-ray disc'),
    ('Enhanced CD', 'physical', 'CD with additional data content'),
    ('HDCD', 'physical', 'High Definition Compatible Digital'),
    ('Hybrid SACD', 'physical', 'SACD with CD-compatible layer'),
    ('Other', 'other', 'Other format not listed')
ON CONFLICT (name) DO NOTHING;


-- Release packaging lookup (from MusicBrainz)
CREATE TABLE IF NOT EXISTS release_packaging (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed common packaging types from MusicBrainz
INSERT INTO release_packaging (name, description) VALUES
    ('Jewel Case', 'Standard CD jewel case'),
    ('Slim Jewel Case', 'Slim-line jewel case'),
    ('Digipak', 'Cardboard/paper folding case'),
    ('Cardboard/Paper Sleeve', 'Simple paper or cardboard sleeve'),
    ('Keep Case', 'Standard DVD/Blu-ray case'),
    ('None', 'No packaging (digital releases)'),
    ('Gatefold Cover', 'Folding cover, typically for vinyl'),
    ('Box', 'Box set packaging'),
    ('Book', 'Book-style packaging'),
    ('Plastic Sleeve', 'Plastic protective sleeve'),
    ('Other', 'Other packaging type')
ON CONFLICT (name) DO NOTHING;


-- ============================================================================
-- MAIN RELEASES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- MusicBrainz identification
    musicbrainz_release_id VARCHAR(36) UNIQUE,
    musicbrainz_release_group_id VARCHAR(36),
    
    -- Release information
    title VARCHAR(500) NOT NULL,
    artist_credit VARCHAR(500),
    disambiguation VARCHAR(500),
    
    -- Release event information
    release_date DATE,
    release_year INTEGER,
    country VARCHAR(2),
    
    -- Label and catalog information
    label VARCHAR(255),
    catalog_number VARCHAR(100),
    barcode VARCHAR(50),
    
    -- Format and packaging (foreign keys)
    format_id INTEGER REFERENCES release_formats(id),
    packaging_id INTEGER REFERENCES release_packaging(id),
    status_id INTEGER REFERENCES release_statuses(id),
    
    -- Additional metadata
    language VARCHAR(10),
    script VARCHAR(10),
    total_tracks INTEGER,
    total_discs INTEGER DEFAULT 1,
    
    -- Cover art
    cover_art_url VARCHAR(500),
    cover_art_small VARCHAR(500),
    cover_art_medium VARCHAR(500),
    cover_art_large VARCHAR(500),
    
    -- External links
    spotify_album_id VARCHAR(50),
    spotify_album_url VARCHAR(500),
    apple_music_url VARCHAR(500),
    amazon_url VARCHAR(500),
    discogs_url VARCHAR(500),
    
    -- Quality/annotation
    data_quality VARCHAR(50),
    annotation TEXT,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);


-- ============================================================================
-- JUNCTION TABLE: RECORDING <-> RELEASE (Many-to-Many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS recording_releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    
    -- Track position on the release
    disc_number INTEGER DEFAULT 1,
    track_number INTEGER,
    track_position VARCHAR(20),
    
    -- Track-specific information
    track_title VARCHAR(500),
    track_artist_credit VARCHAR(500),
    track_length_ms INTEGER,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate track entries
    UNIQUE (recording_id, release_id, disc_number, track_number)
);


-- ============================================================================
-- RELEASE PERFORMERS (Performers associated with a release)
-- ============================================================================

CREATE TABLE IF NOT EXISTS release_performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID REFERENCES instruments(id) ON DELETE SET NULL,
    role VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, performer_id, instrument_id)
);


-- ============================================================================
-- INDEXES
-- ============================================================================

-- Releases table indexes
CREATE INDEX IF NOT EXISTS idx_releases_musicbrainz_release_id 
    ON releases(musicbrainz_release_id);
CREATE INDEX IF NOT EXISTS idx_releases_musicbrainz_release_group_id 
    ON releases(musicbrainz_release_group_id);
CREATE INDEX IF NOT EXISTS idx_releases_title 
    ON releases(title);
CREATE INDEX IF NOT EXISTS idx_releases_artist_credit 
    ON releases(artist_credit);
CREATE INDEX IF NOT EXISTS idx_releases_release_year 
    ON releases(release_year);
CREATE INDEX IF NOT EXISTS idx_releases_label 
    ON releases(label);
CREATE INDEX IF NOT EXISTS idx_releases_barcode 
    ON releases(barcode);
CREATE INDEX IF NOT EXISTS idx_releases_spotify_album_id 
    ON releases(spotify_album_id);

-- Recording-releases junction table indexes
CREATE INDEX IF NOT EXISTS idx_recording_releases_recording_id 
    ON recording_releases(recording_id);
CREATE INDEX IF NOT EXISTS idx_recording_releases_release_id 
    ON recording_releases(release_id);

-- Release performers indexes
CREATE INDEX IF NOT EXISTS idx_release_performers_release_id 
    ON release_performers(release_id);
CREATE INDEX IF NOT EXISTS idx_release_performers_performer_id 
    ON release_performers(performer_id);
CREATE INDEX IF NOT EXISTS idx_release_performers_role 
    ON release_performers(role);


-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger to update updated_at timestamp on releases
CREATE OR REPLACE FUNCTION update_releases_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_releases_updated_at ON releases;
CREATE TRIGGER trigger_releases_updated_at
    BEFORE UPDATE ON releases
    FOR EACH ROW
    EXECUTE FUNCTION update_releases_updated_at();


-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE releases IS 
    'MusicBrainz Release entities - specific product releases (albums, CDs, digital releases)';
COMMENT ON TABLE recording_releases IS 
    'Junction table linking recordings to releases with track position info';
COMMENT ON TABLE release_performers IS 
    'Junction table linking performers to releases with their instrument roles';
COMMENT ON TABLE release_statuses IS 
    'Lookup table for release status (official, promotional, bootleg, pseudo-release)';
COMMENT ON TABLE release_formats IS 
    'Lookup table for medium formats (CD, vinyl, digital, etc.)';
COMMENT ON TABLE release_packaging IS 
    'Lookup table for physical packaging types (jewel case, digipak, etc.)';

COMMENT ON COLUMN releases.musicbrainz_release_id IS 
    'MusicBrainz Release MBID - unique identifier for this specific release';
COMMENT ON COLUMN releases.musicbrainz_release_group_id IS 
    'MusicBrainz Release Group MBID - groups together different editions of the same album';


-- ============================================================================
-- VERIFICATION (uncomment to run)
-- ============================================================================

-- SELECT 
--     'release_statuses' as table_name, COUNT(*) as row_count FROM release_statuses
-- UNION ALL SELECT 'release_formats', COUNT(*) FROM release_formats
-- UNION ALL SELECT 'release_packaging', COUNT(*) FROM release_packaging
-- UNION ALL SELECT 'releases', COUNT(*) FROM releases
-- UNION ALL SELECT 'recording_releases', COUNT(*) FROM recording_releases
-- UNION ALL SELECT 'release_performers', COUNT(*) FROM release_performers;



-- Migration: Add Spotify track fields to recording_releases junction table
-- This allows storing the Spotify track ID/URL that links a specific recording
-- to a specific track on a Spotify album (release)

-- Add Spotify track fields
ALTER TABLE recording_releases
ADD COLUMN IF NOT EXISTS spotify_track_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS spotify_track_url VARCHAR(500);

-- Index for quick lookups by Spotify track ID
CREATE INDEX IF NOT EXISTS idx_recording_releases_spotify_track_id 
ON recording_releases(spotify_track_id) 
WHERE spotify_track_id IS NOT NULL;

-- Comment
COMMENT ON COLUMN recording_releases.spotify_track_id IS 'Spotify track ID for this recording on this release';
COMMENT ON COLUMN recording_releases.spotify_track_url IS 'Full Spotify URL to the track';

-- ============================================================================
-- Migration: Recording-Centric Performer Architecture
-- ============================================================================
-- 
-- Purpose: Restructure the data model so that:
--   1. Performers are associated with RECORDINGS (not releases)
--   2. Recordings have a "default_release_id" for Spotify/album art display
--   3. Release-level Spotify/art columns are removed from recordings table
--   4. release_performers is kept but redesignated for release-specific credits
--      (producers, engineers, remasters - NOT the performing musicians)
--
-- This migration:
--   1. Adds default_release_id FK to recordings
--   2. Drops redundant Spotify/album art columns from recordings
--   3. Updates comments to clarify the new architecture
--
-- ============================================================================

-- ============================================================================
-- STEP 1: Add default_release_id to recordings
-- ============================================================================

-- Add the foreign key column (nullable - not all recordings have releases yet)
ALTER TABLE recordings
ADD COLUMN IF NOT EXISTS default_release_id UUID REFERENCES releases(id) ON DELETE SET NULL;

-- Add index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_recordings_default_release_id 
    ON recordings(default_release_id) 
    WHERE default_release_id IS NOT NULL;

-- Add comment
COMMENT ON COLUMN recordings.default_release_id IS 
    'The preferred release for this recording (provides Spotify URL, album art). '
    'Typically the release with best Spotify match or most complete data.';


-- ============================================================================
-- STEP 2: Drop redundant columns from recordings
-- ============================================================================

-- These columns are now sourced from the default_release (or best available release)
-- Data loss is acceptable per user requirements (will re-import)

DROP VIEW songs_with_canonical_recordings;
ALTER TABLE recordings
DROP COLUMN IF EXISTS spotify_track_id,
DROP COLUMN IF EXISTS album_art_small,
DROP COLUMN IF EXISTS album_art_medium,
DROP COLUMN IF EXISTS album_art_large,
DROP COLUMN IF EXISTS spotify_url;


-- ============================================================================
-- STEP 3: Update table comments to reflect new architecture
-- ============================================================================

COMMENT ON TABLE recordings IS 
    'A specific audio recording of a song. Performers are linked via recording_performers. '
    'Spotify/album art comes from the default_release or is computed from linked releases.';

COMMENT ON TABLE recording_performers IS 
    'Junction table linking performers to recordings with their instrument and role. '
    'This is the PRIMARY source of performer information for a recording.';

COMMENT ON TABLE release_performers IS 
    'Junction table for RELEASE-SPECIFIC credits only. Use for producers, engineers, '
    'remaster credits, liner notes authors, etc. - NOT for performing musicians. '
    'Performing musicians should be linked via recording_performers.';


-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Uncomment to verify the changes:
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'recordings'
-- ORDER BY ordinal_position;

-- Check that default_release_id exists:
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'recordings' AND column_name = 'default_release_id';

-- Verify dropped columns are gone:
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'recordings' AND column_name IN ('spotify_track_id', 'album_art_small', 'album_art_medium', 'album_art_large', 'spotify_url');

-- Migration: Add alternative titles to songs table
-- Description: Adds alt_titles column to store alternative/variant titles for songs
-- This helps with Spotify track matching when songs have different naming conventions
-- Example: "Black and Blue" vs "(What Did I Do To Be So) Black and Blue"

-- Add alt_titles column as a text array
ALTER TABLE songs ADD COLUMN IF NOT EXISTS alt_titles TEXT[];

-- Add comment for documentation
COMMENT ON COLUMN songs.alt_titles IS 'Alternative titles for the song (for matching variations like "Black and Blue" vs "(What Did I Do To Be So) Black and Blue")';

-- Create GIN index for efficient array searches (useful if we ever search by alt title)
CREATE INDEX IF NOT EXISTS idx_songs_alt_titles ON songs USING GIN (alt_titles);

-- Add unique constraint on (recording_id, release_id)
ALTER TABLE recording_releases 
ADD CONSTRAINT recording_releases_recording_release_unique 
UNIQUE (recording_id, release_id);


-- ============================================================================
-- Migration: Add Release Imagery Support
-- Description: Creates release_imagery table to store cover art from multiple
--              sources (CAA, Spotify, Wikipedia, Apple, Amazon) and adds
--              cover_art_checked_at timestamp to releases table.
-- ============================================================================

-- ============================================================================
-- STEP 1: Create imagery_source enum type
-- ============================================================================

-- Create enum type for image sources
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'imagery_source') THEN
        CREATE TYPE imagery_source AS ENUM (
            'MusicBrainz',   -- Cover Art Archive (via MusicBrainz)
            'Spotify',
            'Wikipedia',
            'Apple',
            'Amazon'
        );
    END IF;
END $$;

-- Create enum type for image types
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'imagery_type') THEN
        CREATE TYPE imagery_type AS ENUM (
            'Front',
            'Back'
        );
    END IF;
END $$;


-- ============================================================================
-- STEP 2: Create release_imagery table
-- ============================================================================

CREATE TABLE IF NOT EXISTS release_imagery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign key to releases table
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    
    -- Source identification
    source imagery_source NOT NULL,
    source_id VARCHAR(255),           -- e.g., CAA image ID, Spotify album ID
    source_url VARCHAR(1000),         -- Canonical URL at the source
    
    -- Image type
    type imagery_type NOT NULL,
    
    -- Image URLs at different sizes
    image_url_small VARCHAR(1000),    -- ~250px
    image_url_medium VARCHAR(1000),   -- ~500px  
    image_url_large VARCHAR(1000),    -- ~1200px or original
    
    -- Deduplication/verification
    checksum VARCHAR(64),             -- SHA-256 or MD5 from source (CAA provides this)
    
    -- Metadata
    comment TEXT,                     -- Free text comment from source
    approved BOOLEAN DEFAULT true,    -- Whether approved by source (CAA has this)
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Uniqueness: one image per (release, source, type)
    CONSTRAINT release_imagery_unique UNIQUE (release_id, source, type)
);


-- ============================================================================
-- STEP 3: Create indexes
-- ============================================================================

-- Index for looking up imagery by release
CREATE INDEX IF NOT EXISTS idx_release_imagery_release_id 
    ON release_imagery(release_id);

-- Index for looking up imagery by source
CREATE INDEX IF NOT EXISTS idx_release_imagery_source 
    ON release_imagery(source);

-- Index for looking up imagery by type
CREATE INDEX IF NOT EXISTS idx_release_imagery_type 
    ON release_imagery(type);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_release_imagery_release_source 
    ON release_imagery(release_id, source);


-- ============================================================================
-- STEP 4: Add cover_art_checked_at to releases table
-- ============================================================================

-- Add column to track when we last checked for cover art
ALTER TABLE releases
ADD COLUMN IF NOT EXISTS cover_art_checked_at TIMESTAMP WITH TIME ZONE;

-- Index for finding releases that haven't been checked
CREATE INDEX IF NOT EXISTS idx_releases_cover_art_checked_at 
    ON releases(cover_art_checked_at) 
    WHERE cover_art_checked_at IS NULL;


-- ============================================================================
-- STEP 5: Create trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_release_imagery_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_release_imagery_updated_at ON release_imagery;
CREATE TRIGGER trigger_release_imagery_updated_at
    BEFORE UPDATE ON release_imagery
    FOR EACH ROW
    EXECUTE FUNCTION update_release_imagery_updated_at();


-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE release_imagery IS 
    'Cover art images for releases from multiple sources (CAA, Spotify, etc.)';

COMMENT ON COLUMN release_imagery.release_id IS 
    'The release this image belongs to';

COMMENT ON COLUMN release_imagery.source IS 
    'Source of the image (MusicBrainz/CAA, Spotify, Wikipedia, Apple, Amazon)';

COMMENT ON COLUMN release_imagery.source_id IS 
    'Identifier at the source (e.g., CAA image ID, Spotify album ID)';

COMMENT ON COLUMN release_imagery.source_url IS 
    'Canonical URL to the image page at the source';

COMMENT ON COLUMN release_imagery.type IS 
    'Type of cover art (Front or Back)';

COMMENT ON COLUMN release_imagery.image_url_small IS 
    'URL to small thumbnail (~250px)';

COMMENT ON COLUMN release_imagery.image_url_medium IS 
    'URL to medium image (~500px)';

COMMENT ON COLUMN release_imagery.image_url_large IS 
    'URL to large/original image (~1200px)';

COMMENT ON COLUMN release_imagery.checksum IS 
    'Checksum from source for deduplication (e.g., SHA-256 from CAA)';

COMMENT ON COLUMN release_imagery.approved IS 
    'Whether the image was approved by the source system';

COMMENT ON COLUMN releases.cover_art_checked_at IS 
    'When we last checked for cover art for this release (NULL = never checked)';


-- ============================================================================
-- VERIFICATION (uncomment to run)
-- ============================================================================

-- Check table was created
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'release_imagery'
-- ORDER BY ordinal_position;

-- Check releases column was added
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'releases' AND column_name = 'cover_art_checked_at';

-- Check indexes
-- SELECT indexname FROM pg_indexes WHERE tablename = 'release_imagery';


-- ============================================================================
-- Migration: Add MusicBrainz metadata fields to performers
-- Description: Adds sort_name, artist_type, and disambiguation fields
-- ============================================================================

-- Add sort_name column (e.g., "Davis, Miles" for "Miles Davis")
ALTER TABLE performers ADD COLUMN IF NOT EXISTS sort_name VARCHAR(255);

-- Add artist_type column (Person, Group, Orchestra, etc.)
ALTER TABLE performers ADD COLUMN IF NOT EXISTS artist_type VARCHAR(50);

-- Add disambiguation column (helpful text to identify artist)
ALTER TABLE performers ADD COLUMN IF NOT EXISTS disambiguation VARCHAR(500);

-- Add index for sort_name since it will be used for sorting
CREATE INDEX IF NOT EXISTS idx_performers_sort_name ON performers(sort_name) WHERE sort_name IS NOT NULL;

-- Expression index for sorting by COALESCE(sort_name, name) - used by /performers/index
CREATE INDEX IF NOT EXISTS idx_performers_sort_order ON performers(COALESCE(sort_name, name));

-- Add comments for documentation
COMMENT ON COLUMN performers.sort_name IS 'MusicBrainz sort name for sorting (e.g., "Davis, Miles" for "Miles Davis")';
COMMENT ON COLUMN performers.artist_type IS 'MusicBrainz artist type: Person, Group, Orchestra, Choir, Character, Other';
COMMENT ON COLUMN performers.disambiguation IS 'MusicBrainz disambiguation text to help identify artist (e.g., "jazz trumpeter, bandleader")';


-- ============================================================================
-- Migration: Add Streaming Service Links (Normalized)
-- Description: Creates normalized tables for streaming service links (Spotify,
--              Apple Music, YouTube, etc.) instead of per-service columns.
--              This replaces the pattern of adding spotify_album_id,
--              apple_music_url, etc. as separate columns.
-- ============================================================================

-- ============================================================================
-- STEP 1: Create release_streaming_links table (album-level)
-- ============================================================================

CREATE TABLE IF NOT EXISTS release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign key to releases table
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,

    -- Service identification
    service VARCHAR(50) NOT NULL,         -- 'spotify', 'apple_music', 'youtube_music', 'tidal', 'amazon_music', etc.

    -- Service-specific identifiers
    service_id VARCHAR(100),              -- Album/collection ID on this service
    service_url VARCHAR(500),             -- Direct URL to album on this service

    -- Matching metadata
    match_confidence DECIMAL(3,2),        -- 0.00-1.00, confidence in the match
    match_method VARCHAR(100),            -- How the match was made: 'fuzzy_search', 'isrc', 'manual', etc.
    matched_at TIMESTAMP WITH TIME ZONE,  -- When the match was made
    last_verified_at TIMESTAMP WITH TIME ZONE,  -- Last time we confirmed link still works

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- One link per service per release
    CONSTRAINT release_streaming_links_unique UNIQUE (release_id, service)
);

-- Indexes for release_streaming_links
CREATE INDEX IF NOT EXISTS idx_release_streaming_links_release_id
    ON release_streaming_links(release_id);

CREATE INDEX IF NOT EXISTS idx_release_streaming_links_service
    ON release_streaming_links(service);

CREATE INDEX IF NOT EXISTS idx_release_streaming_links_service_id
    ON release_streaming_links(service_id)
    WHERE service_id IS NOT NULL;

-- Trigger for updated_at
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


-- ============================================================================
-- STEP 2: Create recording_release_streaming_links table (track-level)
-- ============================================================================

CREATE TABLE IF NOT EXISTS recording_release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign key to recording_releases junction table
    recording_release_id UUID NOT NULL REFERENCES recording_releases(id) ON DELETE CASCADE,

    -- Service identification
    service VARCHAR(50) NOT NULL,         -- 'spotify', 'apple_music', 'youtube_music', etc.

    -- Service-specific identifiers
    service_id VARCHAR(100),              -- Track/song ID on this service
    service_url VARCHAR(500),             -- Direct URL to track on this service

    -- Track-specific metadata from service
    duration_ms INTEGER,                  -- Track duration in milliseconds
    popularity INTEGER,                   -- Popularity score (Spotify provides 0-100)
    preview_url VARCHAR(500),             -- 30-second preview URL if available
    isrc VARCHAR(20),                     -- ISRC code if provided by service

    -- Matching metadata
    match_confidence DECIMAL(3,2),        -- 0.00-1.00, confidence in the match
    match_method VARCHAR(100),            -- How the match was made
    matched_at TIMESTAMP WITH TIME ZONE,
    last_verified_at TIMESTAMP WITH TIME ZONE,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- One link per service per recording-release
    CONSTRAINT recording_release_streaming_links_unique UNIQUE (recording_release_id, service)
);

-- Indexes for recording_release_streaming_links
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

-- Trigger for updated_at
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


-- ============================================================================
-- STEP 3: Add documentation comments
-- ============================================================================

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


-- ============================================================================
-- Verification queries (run manually after migration)
-- ============================================================================

-- Check tables were created:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name IN ('release_streaming_links', 'recording_release_streaming_links');

-- Check indexes:
-- SELECT indexname FROM pg_indexes
-- WHERE tablename IN ('release_streaming_links', 'recording_release_streaming_links');


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