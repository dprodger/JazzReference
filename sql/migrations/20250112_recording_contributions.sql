-- Migration: Add Recording Contributions Table
-- Date: 2025-01-12
-- Description: Adds user-contributed metadata for recordings (key, tempo, instrumental/vocal).
--              Uses simple majority consensus for aggregated values.

-- 1. Create the contributions table
CREATE TABLE recording_contributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign keys
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Contributed values (all nullable - user can contribute any subset)
    performance_key VARCHAR(3),  -- C, Db, D, Eb, E, F, Gb, G, Ab, A, Bb, B (using flats)
    tempo_bpm INTEGER,           -- 40-400 BPM range
    is_instrumental BOOLEAN,     -- true = instrumental, false = vocal

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- One contribution per user per recording
    CONSTRAINT unique_user_recording UNIQUE (user_id, recording_id),

    -- Validate key values (using flats for consistency)
    CONSTRAINT valid_performance_key CHECK (
        performance_key IS NULL OR
        performance_key IN ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')
    ),

    -- Validate tempo range
    CONSTRAINT valid_tempo CHECK (
        tempo_bpm IS NULL OR (tempo_bpm >= 40 AND tempo_bpm <= 400)
    )
);

-- 2. Create indexes for efficient queries
CREATE INDEX idx_recording_contributions_recording_id
    ON recording_contributions(recording_id);

CREATE INDEX idx_recording_contributions_user_id
    ON recording_contributions(user_id);

-- Partial indexes for consensus queries (only index non-null values)
CREATE INDEX idx_recording_contributions_key
    ON recording_contributions(recording_id, performance_key)
    WHERE performance_key IS NOT NULL;

CREATE INDEX idx_recording_contributions_tempo
    ON recording_contributions(recording_id, tempo_bpm)
    WHERE tempo_bpm IS NOT NULL;

CREATE INDEX idx_recording_contributions_instrumental
    ON recording_contributions(recording_id, is_instrumental)
    WHERE is_instrumental IS NOT NULL;

-- 3. Create trigger for auto-updating updated_at
CREATE TRIGGER update_recording_contributions_updated_at
    BEFORE UPDATE ON recording_contributions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 4. Add table and column comments
COMMENT ON TABLE recording_contributions IS
    'User-contributed metadata for recordings (key, tempo, instrumental). One row per user per recording.';

COMMENT ON COLUMN recording_contributions.performance_key IS
    'Musical key of this recording performance. Uses flat notation (Db, Eb, Gb, Ab, Bb).';

COMMENT ON COLUMN recording_contributions.tempo_bpm IS
    'Tempo in beats per minute. Typical jazz range: 60-300 BPM.';

COMMENT ON COLUMN recording_contributions.is_instrumental IS
    'True if instrumental, false if includes vocals.';

-- 5. Verification query
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'recording_contributions'
    ) THEN
        RAISE NOTICE 'SUCCESS: recording_contributions table created';
    ELSE
        RAISE EXCEPTION 'FAILED: recording_contributions table not found';
    END IF;
END $$;
