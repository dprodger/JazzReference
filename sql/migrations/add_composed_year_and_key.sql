-- Migration: Add composed_year and composed_key columns to songs table
-- GitHub issues: #17 (Composed In Key), #30 (Composition Year)

ALTER TABLE songs ADD COLUMN IF NOT EXISTS composed_year INTEGER;
ALTER TABLE songs ADD COLUMN IF NOT EXISTS composed_key VARCHAR(10);

-- Add comments for documentation
COMMENT ON COLUMN songs.composed_year IS 'Year the song was originally composed';
COMMENT ON COLUMN songs.composed_key IS 'Original key the song was composed in (e.g., C, Bb, F#m)';

select * from songs where title = 'An Affair to Remember'
update songs set composed_key = 'FΔ' where id = '1fab7d72-030f-4a28-9952-bbadbff69f08'

