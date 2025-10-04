-- drop views
DROP VIEW IF EXISTS performer_discography;
DROP VIEW IF EXISTS songs_with_canonical_recordings;

DROP TRIGGER IF EXISTS update_songs_updated_at ON songs;
DROP TRIGGER IF EXISTS update_performers_updated_at ON performers;
DROP TRIGGER IF EXISTS update_recordings_updated_at ON recordings;
DROP TRIGGER IF EXISTS update_videos_updated_at ON videos;
DROP TRIGGER IF EXISTS update_admin_users_updated_at ON admin_users;

-- Song indexes
DROP INDEX IF EXISTS idx_songs_title;
DROP INDEX IF EXISTS idx_songs_composer;

-- Performer indexes
DROP INDEX IF EXISTS idx_performers_name;

-- Recording indexes
DROP INDEX IF EXISTS idx_recordings_song_id;
DROP INDEX IF EXISTS idx_recordings_year;
DROP INDEX IF EXISTS idx_recordings_is_canonical;
DROP INDEX IF EXISTS idx_recordings_album_title;

-- Recording performer indexes
DROP INDEX IF EXISTS idx_recording_performers_recording_id;
DROP INDEX IF EXISTS idx_recording_performers_performer_id;
DROP INDEX IF EXISTS idx_recording_performers_instrument_id;

-- Video indexes
DROP INDEX IF EXISTS idx_videos_song_id;
DROP INDEX IF EXISTS idx_videos_recording_id;
DROP INDEX IF EXISTS idx_videos_type;

-- Instrument indexes
DROP INDEX IF EXISTS idx_instruments_name;
DROP INDEX IF EXISTS idx_instruments_category;


DROP TABLE IF EXISTS songs CASCADE;
DROP TABLE IF EXISTS performers CASCADE;
DROP TABLE IF EXISTS instruments CASCADE;
DROP TABLE IF EXISTS performer_instruments CASCADE;
DROP TABLE IF EXISTS recordings CASCADE;
DROP TABLE IF EXISTS recording_performers CASCADE;
DROP TABLE IF EXISTS videos CASCADE;
DROP TABLE IF EXISTS video_performers CASCADE;
DROP TABLE IF EXISTS admin_users CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;

