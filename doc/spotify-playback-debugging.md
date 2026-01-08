# Spotify Playback Debugging

## Issue
When clicking a play button on a Recording, sometimes Spotify opens and plays the track automatically, other times it opens to the album but doesn't start playing.

## Root Cause
The app uses two types of Spotify URLs:

1. **Track URL** (`spotify:track:xxx` or `open.spotify.com/track/xxx`)
   - Opens Spotify and **auto-plays** the specific track
   - Stored in: `recording_releases.spotify_track_url`

2. **Album URL** (`spotify:album:xxx` or `open.spotify.com/album/xxx`)
   - Opens the album but **does NOT auto-play**
   - Stored in: `releases.spotify_album_url`

## How the URL is Selected

### Backend (songs.py:270-285)
```sql
COALESCE(rr_sub.spotify_track_url, rel_sub.spotify_album_url)
```
Prefers track URL, falls back to album URL.

### iOS App (Models.swift:191-205)
```swift
var bestSpotifyUrl: String? {
    // First try API-provided best URL
    if let apiUrl = bestSpotifyUrlFromRelease {
        return apiUrl
    }
    // Then try track URL (will auto-play)
    if let release = sortedReleases?.first(where: { $0.spotifyTrackUrl != nil }) {
        return release.spotifyTrackUrl
    }
    // Fall back to album URL (won't auto-play)
    if let release = sortedReleases?.first(where: { $0.spotifyAlbumUrl != nil }) {
        return release.spotifyAlbumUrl
    }
    return nil
}
```

## Why Some Recordings Lack Track URLs
The `spotify_track_url` is populated by the Spotify matcher when it confidently matches a specific track. If the matcher:
- Found the album but couldn't confidently match the track
- Or the matching was done at album-level only

...then only `spotify_album_url` exists, and playback won't auto-start.

## Potential Solutions

### 1. Improve Track Matching
Make the Spotify matcher more aggressive about matching tracks within already-matched albums. Look at:
- `backend/spotify_matcher.py`
- `backend/spotify_utils.py`

### 2. Use Spotify Play Context
When opening an album URL, try appending track context:
```
spotify:album:xxx?track=0
```
Note: May not work reliably if track order differs between MusicBrainz and Spotify.

### 3. Visual Indicator in UI
Show different icons for:
- Track link (will play) - e.g., play icon
- Album link (won't auto-play) - e.g., album icon with play badge

This sets user expectations appropriately.

### 4. Query to Find Affected Recordings
```sql
-- Recordings with album URL but no track URL
SELECT r.id, r.album_title, rel.title as release_title, rel.spotify_album_url
FROM recordings r
JOIN recording_releases rr ON rr.recording_id = r.id
JOIN releases rel ON rr.release_id = rel.id
WHERE rel.spotify_album_url IS NOT NULL
  AND rr.spotify_track_url IS NULL;
```

## Related Files
- `backend/routes/songs.py` - best_spotify_url subquery
- `backend/spotify_matcher.py` - track matching logic
- `iOS-app/JazzReference/Support_Files/Models.swift` - bestSpotifyUrl computed property
- `iOS-app/JazzReference/RecordingDetailView.swift` - play button UI
