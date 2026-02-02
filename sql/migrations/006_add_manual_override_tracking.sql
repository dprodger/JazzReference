-- ============================================================================
-- Migration: Add Manual Override Tracking for Streaming Links
-- Date: 2025-02-02
-- Description: Adds user tracking columns to streaming link tables so that
--              manual overrides (match_method='manual') can be attributed to
--              specific users and protected from bulk re-matching operations.
-- ============================================================================

-- STEP 1: Add columns to release_streaming_links (album-level)
ALTER TABLE release_streaming_links
ADD COLUMN IF NOT EXISTS added_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS notes TEXT;

-- STEP 2: Add columns to recording_release_streaming_links (track-level)
ALTER TABLE recording_release_streaming_links
ADD COLUMN IF NOT EXISTS added_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS notes TEXT;

-- STEP 3: Add indexes for querying manual overrides by user
CREATE INDEX IF NOT EXISTS idx_release_streaming_links_added_by_user
    ON release_streaming_links(added_by_user_id)
    WHERE added_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_added_by_user
    ON recording_release_streaming_links(added_by_user_id)
    WHERE added_by_user_id IS NOT NULL;

-- STEP 4: Add indexes for querying by match_method (useful for finding manual overrides)
CREATE INDEX IF NOT EXISTS idx_release_streaming_links_match_method
    ON release_streaming_links(match_method)
    WHERE match_method IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rr_streaming_links_match_method
    ON recording_release_streaming_links(match_method)
    WHERE match_method IS NOT NULL;

-- STEP 5: Add documentation comments
COMMENT ON COLUMN release_streaming_links.added_by_user_id IS
    'User who added this link manually. NULL for auto-matched links.';

COMMENT ON COLUMN release_streaming_links.notes IS
    'Optional notes explaining why this manual override was made.';

COMMENT ON COLUMN recording_release_streaming_links.added_by_user_id IS
    'User who added this link manually. NULL for auto-matched links.';

COMMENT ON COLUMN recording_release_streaming_links.notes IS
    'Optional notes explaining why this manual override was made.';

-- ============================================================================
-- Usage Notes:
--
-- Manual overrides should be created with:
--   match_method = 'manual'
--   added_by_user_id = <user UUID>
--   match_confidence = 1.0 (human-verified)
--
-- To find all manual overrides:
--   SELECT * FROM release_streaming_links WHERE match_method = 'manual';
--   SELECT * FROM recording_release_streaming_links WHERE match_method = 'manual';
--
-- To find overrides by a specific user:
--   SELECT * FROM release_streaming_links WHERE added_by_user_id = '<user_id>';
--
-- Matching code should check match_method before overwriting:
--   IF existing.match_method = 'manual' THEN skip
-- ============================================================================
