# Spotify Link Audit Notes

**Created:** 2024-12-22
**Status:** Needs investigation
**Related:** Streaming availability admin tool discrepancy

## Summary

There's a discrepancy between what the streaming availability admin tool reports and what the iOS app shows as "playable" on Spotify. The admin tool counts only track-level matches, while the app falls back to album-level links.

## Key Findings

### 1. Two Levels of Spotify Links

**Track-level** (`recording_releases.spotify_track_id`):
- Direct link to the specific track on Spotify
- Most accurate - takes user directly to the song
- Set by the Spotify matcher when it successfully matches a track

**Album-level** (`releases.spotify_album_id`):
- Link to the album containing the track
- Fallback when track matching fails
- User lands on album page, must find the track manually

### 2. How the App Displays Spotify Links

The API queries in `routes/songs.py` use a COALESCE pattern:

```sql
CASE
    WHEN rr.spotify_track_id IS NOT NULL
        THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
    WHEN rel.spotify_album_id IS NOT NULL
        THEN 'https://open.spotify.com/album/' || rel.spotify_album_id
END as best_spotify_url
```

This means:
- If track-level exists → show track link
- Else if album-level exists → show album link as fallback
- The app shows both as "playable" even though album-level is less precise

### 3. Streaming Availability Admin Tool

The admin tool (`/admin/streaming-availability`) only counts track-level matches:

```sql
COUNT(DISTINCT CASE
    WHEN rr.spotify_track_id IS NOT NULL THEN r.id
END) as spotify_recordings
```

This causes the discrepancy:
- Admin tool shows: `S: 1` (track-level only)
- App shows: 11 playable (track + album fallback)

### 4. Example: "Don'cha Go 'Way Mad"

| Metric | Count |
|--------|-------|
| Total recordings | 51 |
| Track-level Spotify | 1 |
| Album-level Spotify (no track) | 10 |
| App shows as playable | 11 |
| Admin tool reports | 1 |

### 5. The Real Problem

Many recordings have album-level matches but no track-level matches. This suggests:

1. **Album matching succeeded** - the Spotify matcher found the correct album
2. **Track matching failed** - couldn't match the specific track within the album

Possible reasons for track matching failure:
- Track title differences (e.g., "Don'cha Go 'Way Mad" vs "Don't Go Away Mad")
- Track not on Spotify version of album (different track listing)
- Fuzzy matching threshold not met
- Track matching was never run (only album was matched)

### 6. Spotify Matcher Flow

From `spotify_matcher.py`:

1. `match_releases()` - searches for albums on Spotify
2. If album found → stores `spotify_album_id` on `releases` table
3. `match_tracks_for_release()` - tries to match individual tracks
4. If track found → stores `spotify_track_id` on `recording_releases` table

The album can match successfully while track matching fails.

## Questions to Investigate

1. **Should album-level links count as "playable"?**
   - Pro: User can still find the track manually
   - Con: Not a direct link, poor UX

2. **Why are track matches failing when albums match?**
   - Need to audit specific cases
   - May need to adjust fuzzy matching thresholds
   - May need to handle title variations better

3. **Should we re-run track matching for album-matched releases?**
   - Many releases have album IDs but no track IDs
   - Could improve track-level coverage

4. **Should admin tool show both counts?**
   - Option A: Show combined (match app behavior)
   - Option B: Show separate columns (S Track / S Album)
   - Option B gives better visibility into the gap

## Recommended Actions

1. **Audit album-matched releases without track matches**
   - How many are there?
   - Sample some and check if tracks exist on Spotify
   - Identify patterns in why matching failed

2. **Consider re-running track matcher**
   - For releases that have `spotify_album_id` but recordings lack `spotify_track_id`
   - May recover many track-level matches

3. **Update admin tool** (optional)
   - Add visibility into album-level vs track-level coverage
   - Help identify where track matching needs improvement

## SQL Queries for Investigation

```sql
-- Count releases with album ID but no track matches
SELECT COUNT(DISTINCT rel.id)
FROM releases rel
WHERE rel.spotify_album_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM recording_releases rr
    WHERE rr.release_id = rel.id
      AND rr.spotify_track_id IS NOT NULL
  );

-- Find songs with biggest gap (album matches but no track matches)
SELECT
    s.title,
    s.composer,
    COUNT(DISTINCT r.id) as total_recordings,
    COUNT(DISTINCT CASE WHEN rr.spotify_track_id IS NOT NULL THEN r.id END) as track_level,
    COUNT(DISTINCT CASE WHEN rel.spotify_album_id IS NOT NULL AND rr.spotify_track_id IS NULL THEN r.id END) as album_only
FROM songs s
JOIN recordings r ON r.song_id = s.id
JOIN recording_releases rr ON rr.recording_id = r.id
JOIN releases rel ON rr.release_id = rel.id
GROUP BY s.id, s.title, s.composer
HAVING COUNT(DISTINCT CASE WHEN rel.spotify_album_id IS NOT NULL AND rr.spotify_track_id IS NULL THEN r.id END) > 5
ORDER BY album_only DESC;
```
