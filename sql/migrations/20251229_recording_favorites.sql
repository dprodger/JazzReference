-- ============================================================================
-- Migration: Add Recording Favorites
-- Date: 2025-12-29
-- Description: Creates table for users to favorite recordings (GitHub Issue #34)
-- ============================================================================

-- STEP 1: Create recording_favorites table
CREATE TABLE IF NOT EXISTS recording_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT recording_favorites_unique UNIQUE (recording_id, user_id)
);

-- STEP 2: Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_recording_favorites_recording_id
    ON recording_favorites(recording_id);

CREATE INDEX IF NOT EXISTS idx_recording_favorites_user_id
    ON recording_favorites(user_id);

-- STEP 3: Add documentation comments
COMMENT ON TABLE recording_favorites IS
    'Junction table for user favorite recordings. One row per (recording, user) pair.';

COMMENT ON COLUMN recording_favorites.recording_id IS
    'Reference to the favorited recording';

COMMENT ON COLUMN recording_favorites.user_id IS
    'Reference to the user who favorited the recording';

-- Verification (run after migration)
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name = 'recording_favorites';


select * from recording_favorites

select * from users



SELECT r.id, s.title as song_title, rl.title as album_title,
     r.recording_year,
     COALESCE(ri.image_url_small, rl.cover_art_small) as best_album_art_small,
     rf.created_at as favorited_at
FROM recording_favorites rf
INNER JOIN recordings r ON rf.recording_id = r.id
LEFT JOIN songs s ON r.song_id = s.id
LEFT JOIN releases rl ON r.default_release_id = rl.id
LEFT JOIN release_imagery ri ON rl.id = ri.release_id AND ri.type = 'Front'
LIMIT 5
