-- Migration: Add composed_year and composed_key columns to songs table
-- GitHub issues: #17 (Composed In Key), #30 (Composition Year)

ALTER TABLE songs ADD COLUMN IF NOT EXISTS composed_year INTEGER;
ALTER TABLE songs ADD COLUMN IF NOT EXISTS composed_key VARCHAR(10);

-- Add comments for documentation
COMMENT ON COLUMN songs.composed_year IS 'Year the song was originally composed';
COMMENT ON COLUMN songs.composed_key IS 'Original key the song was composed in (e.g., C, Bb, F#m)';

select * from songs where title like '%Wonderful'
update songs set composed_key = 'FΔ' where id = '1fab7d72-030f-4a28-9952-bbadbff69f08'


select id, title, composer, composed_key from songs





select * from songs where title = 'Strasbourg/St. Denis'
update songs set composed_year=2007 where id = '54b273b2-e3d6-440d-93c4-8cf5f551200a'

update songs set title = '(I Don’t Stand) A Ghost of a Chance', alt_titles = ARRAY['Ghost of a Chance'], musicbrainz_id = 'ade9c30c-faf5-3219-aa4a-6631d39deea7', composed_year = null
where id = '69ee17b6-fae6-4835-9844-a24e2d10651b'

delete from recordings where song_id = '69ee17b6-fae6-4835-9844-a24e2d10651b' and source_mb_work_id = 'bd031d95-bfc5-3ab8-85e9-89d85da5c5d5'


update songs set musicbrainz_id = 'f583f1d2-a199-3c7b-b8bd-6a61b1d3e0cb', second_mb_id = 'd956f515-1258-4ffe-a3f6-b62bdce7ce61'
where id = '2054bc9f-438e-4525-957f-27dccec4860b'
