#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <song_name>"
    echo "Example: $0 'All The Things You Are'"
    exit 1
fi

SONG_NAME="$1"

python import_mb_releases.py --name "$SONG_NAME" --force-refresh --limit 2000
python match_spotify_tracks.py --name "$SONG_NAME" --force-refresh --rematch-all
python match_apple_tracks.py --name "$SONG_NAME" --force-refresh
python jazzs_extract.py --name "$SONG_NAME" --force-refresh
python jazzs_match_authorityrecs.py --name "$SONG_NAME" 
