# Spotify Link Audit Notes

## 2024-12-24: Data Model Considerations for Compilations and Supersets

### The Problem

When a MusicBrainz release is a compilation or superset that doesn't have an exact Spotify equivalent, the current matching can be misleading.

**Example case: Julie London "Julie Is Her Name" releases**

- MusicBrainz has 3 releases that are compilations/expanded editions containing the track "Don'cha Go 'Way Mad"
- Spotify has "Julie Is Her Name, Vol. 1" and "Julie Is Her Name, Vol. 2" as separate albums
- Our matcher linked all 3 MB releases to Spotify's "Vol. 2"
- This is correct for tracks that appear on Vol. 2, but misleading for:
  - Tracks that are on the MB compilation but only on Spotify's Vol. 1
  - Tracks that are on the MB compilation but not on Spotify at all
  - The album-level metadata (cover art, album title) which suggests Vol. 2 when it's actually a different/larger release

### Current Data Model

```
releases.spotify_album_id           -> "This MB release is linked to this Spotify album"
recording_releases.spotify_track_id -> "This specific recording on this release has this Spotify track"
```

**What works:** Track-level matching (`spotify_track_id`) is accurate. If a track exists on both the MB release and the matched Spotify album, we get a track ID. If not, no track ID is set.

**What's misleading:** Album-level link (`spotify_album_id`) suggests the MB release and Spotify album are equivalent when they may not be. This affects:
- Cover art display (showing Vol. 2 art for a compilation)
- Album title display
- User expectations when browsing the release

### Recent Change (2024-12-24)

Updated `has_spotify` definition across the codebase to only return true when there's a **track-level match** (`spotify_track_id` exists), not just an album-level match. This ensures playability indicators are accurate.

Files changed:
- `routes/songs.py` - `has_spotify` SQL
- `routes/recordings.py` - per-release `has_spotify`
- `routes/admin.py` - admin display logic
- iOS app `Models.swift` - `Release.hasSpotify`, `Recording.bestSpotifyUrl`
- iOS app `RecordingDetailView.swift` - `displaySpotifyUrl`

### Options Under Consideration

#### Option 1: Stricter Album Matching
Only store `spotify_album_id` for high-confidence album matches (e.g., >85% title similarity). Tracks can still get `spotify_track_id` matched independently.

**Pros:** Clean, simple, avoids misleading album-level links
**Cons:** Fewer album links, potentially affects cover art availability

#### Option 2: Add Confidence/Partial Flag
Store `spotify_match_type: 'exact' | 'partial'` to indicate when it's a superset/subset situation.

**Pros:** Preserves information, UI can communicate uncertainty
**Cons:** More complexity in queries and UI

#### Option 3: Decouple Track Matching from Album Matching
- Album matching stays strict (high confidence only)
- Track matching searches independently by track name + artist
- A track can be playable even if its release has no Spotify album link

**Pros:** Maximum track playability, clean separation of concerns
**Cons:** More Spotify API calls, track might come from a different album than the release

#### Option 4: Multiple Spotify Albums per Release
Allow a Release to have multiple Spotify album IDs. If the combined track count of Spotify albums is less than the MB release track count, we know it's a superset.

**Pros:** Accurate modeling of reality (compilation = Vol. 1 + Vol. 2)
**Cons:** Schema change (junction table), more complex matching/queries/UI

### Current Matching Flow

1. Match MB release to Spotify album
2. If album matched, search that album's tracks for our recording
3. If track found, store `spotify_track_id`

**Issue:** If album match fails or is to the "wrong" album (e.g., Vol. 2 instead of Vol. 1), we may miss track matches.

### Open Questions

1. What's the priority: accurate album metadata or maximum track playability?
2. Should track matching be independent of album matching?
3. How should the UI communicate when an album link is approximate/partial?
4. Is the complexity of multiple Spotify albums per release worth it?

### Also Fixed (2024-12-24): Exact-First Album Matching

Updated `search_spotify_album()` in `spotify_matcher.py` to:
1. Increase search result limit from 5 to 10
2. Check for **exact album title matches** first (case-insensitive)
3. Only fall back to fuzzy matching if no exact match passes validation

This fixed cases like "Julie" by Julie London where Spotify ranked the correct album #10 in results, behind albums like "Julie Is Her Name" that fuzzy-matched better.
