-- ============================================================================
-- Migration: Add service_title to recording_release_streaming_links
-- Date: 2026-03-19
-- Description: Adds a service_title column so we can store the track title
--              as it appears on each streaming service (Spotify, Apple Music,
--              etc.) directly on the streaming link row. Previously this was
--              stored ambiguously in recording_releases.track_title.
-- ============================================================================

-- STEP 1: Add the column
ALTER TABLE recording_release_streaming_links
ADD COLUMN IF NOT EXISTS service_title VARCHAR(500);

-- STEP 2: Backfill from recording_releases.track_title for existing rows.
-- This is a best-effort backfill: recording_releases.track_title was populated
-- by both Spotify and Apple Music matchers, so we copy it to whichever
-- streaming link exists for each recording_release.
UPDATE recording_release_streaming_links rrsl
SET service_title = rr.track_title
FROM recording_releases rr
WHERE rrsl.recording_release_id = rr.id
  AND rr.track_title IS NOT NULL
  AND rrsl.service_title IS NULL;

-- VERIFICATION:
SELECT service, COUNT(*) as total, COUNT(service_title) as with_title
FROM recording_release_streaming_links
GROUP BY service;
