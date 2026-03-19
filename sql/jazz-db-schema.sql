-- Jazz Reference Application - PostgreSQL Database Schema
-- Generated from live Supabase database on 2026-03-18

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable unaccent extension for accent-insensitive text matching
-- (e.g., "Mel Tormé" matches "Mel Torme")
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ============================================================================
-- CUSTOM TYPES
-- ============================================================================

CREATE TYPE imagery_source AS ENUM ('MusicBrainz', 'Spotify', 'Wikipedia', 'Apple', 'Amazon');
CREATE TYPE imagery_type AS ENUM ('Front', 'Back');

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Songs table
CREATE TABLE songs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    composer VARCHAR(500),
    composed_year INTEGER,
    composed_key VARCHAR(10),
    song_reference TEXT,
    structure TEXT,
    external_references JSONB,
    musicbrainz_id VARCHAR(36) UNIQUE,
    second_mb_id VARCHAR(36),
    wikipedia_url VARCHAR(500),
    alt_titles TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Performers table
CREATE TABLE performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sort_name VARCHAR(255),
    artist_type VARCHAR(50),
    disambiguation VARCHAR(500),
    biography TEXT,
    birth_date DATE,
    death_date DATE,
    external_links JSONB,
    wikipedia_url VARCHAR(500),
    musicbrainz_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Instruments table
CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- RELEASE REFERENCE TABLES
-- ============================================================================

CREATE TABLE release_formats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE release_packaging (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE release_statuses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- RELEASES
-- ============================================================================

CREATE TABLE releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    musicbrainz_release_id VARCHAR(36) UNIQUE,
    musicbrainz_release_group_id VARCHAR(36),
    title VARCHAR(500) NOT NULL,
    artist_credit VARCHAR(500),
    disambiguation VARCHAR(500),
    release_date DATE,
    release_year INTEGER,
    country VARCHAR(2),
    label VARCHAR(255),
    catalog_number VARCHAR(100),
    barcode VARCHAR(50),
    format_id INTEGER REFERENCES release_formats(id),
    packaging_id INTEGER REFERENCES release_packaging(id),
    status_id INTEGER REFERENCES release_statuses(id),
    language VARCHAR(10),
    script VARCHAR(10),
    total_tracks INTEGER,
    total_discs INTEGER DEFAULT 1,
    cover_art_url VARCHAR(500),
    cover_art_checked_at TIMESTAMP WITH TIME ZONE,
    spotify_album_id VARCHAR(50),
    spotify_album_url VARCHAR(500),
    apple_music_url VARCHAR(500),
    apple_music_searched_at TIMESTAMP WITH TIME ZONE,
    amazon_url VARCHAR(500),
    discogs_url VARCHAR(500),
    data_quality VARCHAR(50),
    annotation TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- ============================================================================
-- RECORDINGS
-- ============================================================================

CREATE TABLE recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    title VARCHAR(500),                         -- MusicBrainz recording title (may differ from song title)
    recording_date DATE,
    recording_year INTEGER,
    recording_date_source VARCHAR(50),          -- 'mb_performer_relation', 'mb_first_release', 'earliest_release', 'manual'
    recording_date_precision VARCHAR(10),       -- 'day', 'month', 'year'
    mb_first_release_date VARCHAR(10),          -- MusicBrainz first-release-date (YYYY, YYYY-MM, or YYYY-MM-DD)
    label VARCHAR(255),
    is_canonical BOOLEAN DEFAULT false,
    notes TEXT,
    default_release_id UUID REFERENCES releases(id) ON DELETE SET NULL,
    musicbrainz_id VARCHAR(255) UNIQUE,
    source_mb_work_id VARCHAR(36),              -- MusicBrainz work ID this recording was imported from
    duration_ms INTEGER,                        -- Recording duration from MusicBrainz
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- ============================================================================
-- JUNCTION TABLES
-- ============================================================================

-- Recording ↔ Release junction
CREATE TABLE recording_releases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    disc_number INTEGER DEFAULT 1,
    track_number INTEGER,
    track_position VARCHAR(20),                 -- e.g., A1, B2
    track_title VARCHAR(500),                   -- May differ from recording title
    track_artist_credit VARCHAR(500),
    track_length_ms INTEGER,                    -- Duration on this specific release
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recording_id, release_id, disc_number, track_number),
    UNIQUE (recording_id, release_id)
);

-- Recording ↔ Performer junction
CREATE TABLE recording_performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID REFERENCES instruments(id) ON DELETE SET NULL,
    role VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recording_id, performer_id, instrument_id)
);

-- Performer ↔ Instrument junction
CREATE TABLE performer_instruments (
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false,
    proficiency_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (performer_id, instrument_id)
);

-- Release ↔ Performer junction
CREATE TABLE release_performers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    instrument_id UUID REFERENCES instruments(id) ON DELETE SET NULL,
    role VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, performer_id, instrument_id)
);

-- ============================================================================
-- STREAMING LINKS
-- ============================================================================

-- Track-level streaming links (per recording-release pair)
CREATE TABLE recording_release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_release_id UUID NOT NULL REFERENCES recording_releases(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,               -- 'spotify', 'apple_music', 'youtube', 'youtube_music', 'tidal', etc.
    service_id VARCHAR(100),                    -- Track ID on this service
    service_title VARCHAR(500),                -- Track title as it appears on this service
    service_url VARCHAR(500),
    duration_ms INTEGER,
    popularity INTEGER,                         -- Spotify popularity score
    preview_url VARCHAR(500),
    isrc VARCHAR(20),                           -- International Standard Recording Code
    match_confidence NUMERIC,                   -- 0.00-1.00
    match_method VARCHAR(100),                  -- 'fuzzy_search', 'isrc_lookup', 'upc_lookup', 'manual', etc.
    matched_at TIMESTAMP WITH TIME ZONE,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    added_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recording_release_id, service)
);

-- Album-level streaming links (per release)
CREATE TABLE release_streaming_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,
    service_id VARCHAR(100),
    service_url VARCHAR(500),
    match_confidence NUMERIC,
    match_method VARCHAR(100),
    matched_at TIMESTAMP WITH TIME ZONE,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    added_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, service)
);

-- ============================================================================
-- RELEASE METADATA
-- ============================================================================

CREATE TABLE release_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    country VARCHAR(2),
    release_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, country, release_date)
);

CREATE TABLE release_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    label_name VARCHAR(255) NOT NULL,
    catalog_number VARCHAR(100),
    musicbrainz_label_id VARCHAR(36),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, label_name, catalog_number)
);

CREATE TABLE release_imagery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    release_id UUID NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    source imagery_source NOT NULL,
    source_id VARCHAR(255),
    source_url VARCHAR(1000),
    type imagery_type NOT NULL,
    image_url_small VARCHAR(1000),
    image_url_medium VARCHAR(1000),
    image_url_large VARCHAR(1000),
    checksum VARCHAR(64),
    comment TEXT,
    approved BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (release_id, source, type)
);

-- ============================================================================
-- IMAGES
-- ============================================================================

CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url VARCHAR(1000) NOT NULL UNIQUE,
    source VARCHAR(100) NOT NULL,
    source_identifier VARCHAR(255),
    license_type VARCHAR(100),
    license_url VARCHAR(500),
    attribution TEXT,
    width INTEGER,
    height INTEGER,
    thumbnail_url VARCHAR(1000),
    source_page_url VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_identifier, url)
);

CREATE TABLE artist_images (
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (performer_id, image_id)
);

-- ============================================================================
-- USER & AUTH TABLES
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT false,
    password_hash VARCHAR(255),
    display_name VARCHAR(255),
    profile_image_url VARCHAR(500),
    google_id VARCHAR(255) UNIQUE,
    apple_id VARCHAR(255) UNIQUE,
    is_active BOOLEAN DEFAULT true,
    account_locked BOOLEAN DEFAULT false,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'editor',
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    device_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- USER FEATURES
-- ============================================================================

CREATE TABLE repertoires (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE repertoire_songs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repertoire_id UUID NOT NULL REFERENCES repertoires(id) ON DELETE CASCADE,
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repertoire_id, song_id)
);

CREATE TABLE recording_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recording_id, user_id)
);

CREATE TABLE recording_contributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    performance_key VARCHAR(3),
    is_instrumental BOOLEAN,
    tempo_marking VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, recording_id)
);

-- ============================================================================
-- CONTENT TABLES
-- ============================================================================

CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID REFERENCES songs(id) ON DELETE SET NULL,
    recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    youtube_url VARCHAR(500) NOT NULL,
    title VARCHAR(255),
    description TEXT,
    video_type VARCHAR(50) NOT NULL,
    duration_seconds INTEGER,
    tempo INTEGER,
    key_signature VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL
);

CREATE TABLE video_performers (
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    performer_id UUID NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (video_id, performer_id)
);

CREATE TABLE solo_transcriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    recording_id UUID REFERENCES recordings(id) ON DELETE CASCADE,
    youtube_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- ============================================================================
-- DATA QUALITY & ADMIN
-- ============================================================================

CREATE TABLE orphan_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    mb_recording_id VARCHAR(36) NOT NULL,
    mb_recording_title VARCHAR(500),
    mb_artist_credit VARCHAR(500),
    mb_artist_ids TEXT[],
    mb_first_release_date VARCHAR(20),
    mb_release_count INTEGER,
    mb_length_ms INTEGER,
    mb_disambiguation VARCHAR(500),
    mb_releases JSONB,
    spotify_track_id VARCHAR(100),
    spotify_track_name VARCHAR(500),
    spotify_artist_name VARCHAR(500),
    spotify_album_name VARCHAR(500),
    spotify_album_id VARCHAR(100),
    spotify_preview_url VARCHAR(500),
    spotify_external_url VARCHAR(500),
    spotify_album_art_url VARCHAR(500),
    spotify_match_confidence VARCHAR(20),
    spotify_match_score DOUBLE PRECISION,
    spotify_matched_at TIMESTAMP WITH TIME ZONE,
    spotify_matched_mb_release_id VARCHAR(36),
    issue_type VARCHAR(50) NOT NULL,
    linked_work_ids TEXT[],
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(100),
    review_notes TEXT,
    imported_recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    imported_at TIMESTAMP WITH TIME ZONE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (song_id, mb_recording_id)
);

CREATE TABLE song_authority_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    recording_id UUID REFERENCES recordings(id) ON DELETE SET NULL,
    source VARCHAR(100) NOT NULL,
    recommendation_text TEXT,
    source_url TEXT NOT NULL,
    artist_name VARCHAR(255),
    album_title VARCHAR(255),
    recording_year INTEGER,
    itunes_album_id BIGINT,
    itunes_track_id BIGINT,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bad_streaming_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service VARCHAR(50) NOT NULL,
    block_level VARCHAR(20) NOT NULL,
    service_id VARCHAR(100) NOT NULL,
    song_id UUID NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    reason TEXT,
    reported_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (service, block_level, service_id, song_id)
);

CREATE TABLE content_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    entity_name VARCHAR(255) NOT NULL,
    report_category VARCHAR(50) NOT NULL DEFAULT 'link_issue',
    external_source VARCHAR(100) NOT NULL,
    external_url VARCHAR(1000) NOT NULL,
    explanation TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'normal',
    resolution_notes TEXT,
    resolution_action VARCHAR(100),
    reporter_ip VARCHAR(45),
    reporter_user_agent TEXT,
    reporter_platform VARCHAR(50),
    reporter_app_version VARCHAR(50),
    reviewed_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- View for orphan count
CREATE VIEW orphan_count AS
    SELECT COUNT(*) FROM orphan_recordings WHERE status = 'pending';
