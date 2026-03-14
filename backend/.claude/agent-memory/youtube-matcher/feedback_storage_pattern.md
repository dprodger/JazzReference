---
name: YouTube links go in streaming_links table
description: User wants YouTube video links stored in recording_release_streaming_links (service='youtube'), NOT in the videos table. Videos table is for backing tracks and educational content.
type: feedback
---

YouTube video matches for recordings should be stored in `recording_release_streaming_links` with `service = 'youtube'`, following the same pattern as Spotify and Apple Music links. The `videos` table is used for different content types (backing tracks, educational videos, transcriptions) that are linked at the song level, not matched to specific recording releases.

Key fields for YouTube entries in recording_release_streaming_links:
- `service`: 'youtube'
- `service_id`: The 11-character YouTube video ID (e.g., '0PUYu8Wu-W8')
- `service_url`: Full URL like 'https://www.youtube.com/watch?v={id}'
- `duration_ms`: Video duration in milliseconds
- `match_confidence`: 0.0-1.0 (use >= 0.90 for HIGH, 0.75-0.89 for MEDIUM)
- `match_method`: 'yt_search'
- `notes`: Description of why the match was made and confidence reasoning
