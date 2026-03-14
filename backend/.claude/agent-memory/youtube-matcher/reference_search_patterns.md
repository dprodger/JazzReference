---
name: YouTube search patterns for jazz recordings
description: Effective search query patterns and matching strategies for finding jazz recordings on YouTube
type: reference
---

## Search Strategy

1. **Primary search**: `{artist} "{song title}"` with quoted song title
2. **Fallback**: `{artist} {song title}` without quotes if no results
3. Use `yt-dlp --dump-json --flat-playlist --no-download "ytsearch5:{query}"` for searching
4. Use `yt-dlp --dump-json --no-download "https://www.youtube.com/watch?v={id}"` for full metadata verification

## Matching Priority

1. **Topic channels** (auto-generated): Highest reliability. Match album title from description to our release title.
2. **Official artist channels**: High reliability. Verify via "Provided to YouTube by" in description.
3. **Archive channels** (The78Prof, etc.): Good reliability for historical recordings. Verify catalog numbers.
4. **User uploads**: Lower priority. Only use when title, artist, and duration strongly match.

## Confidence Scoring

- **0.95 (HIGH)**: Topic/official channel + song title match + album title match in description
- **0.90 (HIGH)**: Reliable archive channel + artist match + song title match + year match
- **0.80 (MEDIUM)**: User channel with clear metadata but cannot confirm exact release
- **0.75 (MEDIUM)**: Topic channel but cannot confirm which specific release/recording it matches
- **Below 0.70**: Do not store

## Common Pitfalls

- Song title spelling variations: "Sainte Marie" vs "Saint Marie" vs "St. Marie" vs "Ste. Marie" -- all refer to the same song
- Multiple recordings by the same artist (e.g., Frankie Laine recorded this song in both 1946 and 1957)
- Compilation reissues: A Topic channel video may be from a reissue compilation rather than the original release
- Live vs studio: Check for "(Live)" or "Live at" in titles to match to the correct recording type

## Duration Notes

- For this song, no Spotify/Apple Music duration data was available in the streaming links, so duration matching against the DB was not possible
- YouTube durations from Topic channels are reliable and can be stored as duration_ms
- For jazz recordings, typical duration tolerance is +/- 15 seconds for tracks under 10 minutes
