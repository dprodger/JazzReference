#!/bin/bash
# Match Apple Music tracks for all songs in Dave's Ensemble repertoire
# One-time script - December 2025

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "=========================================="
echo "Matching Spotify Music for Dave's Ensemble"
echo "26 songs total"
echo "=========================================="

# Song IDs and titles from Dave's Ensemble repertoire
songs=(
#    "1fab7d72-030f-4a28-9952-bbadbff69f08|An Affair to Remember"
#    "f9c4fa68-498b-4c1e-bb15-04be2c5b4537|Autumn Leaves"
#    "710b3005-c389-4365-b885-56e3f1dc1762|Black and Blue"
#    "9e3a5b18-1f38-462e-9e34-dea319b7fcb2|Black Velvet"
#    "97bbaec0-395f-40ae-b5cd-25c3d6ca0785|Blue, Turning Grey Over You"
#    "2e287025-9996-4fe3-aea6-872cd5f0b70c|Born to be Blue"
#    "9b1887a1-7bf5-44e7-b538-574397539b77|By the River Sainte Marie"
#    "62eeaf0d-b400-4548-9383-f993f8ca3ec1|Corcovado"
#    "ed5c93b9-5d35-47d6-a90f-4d9e9e82d5c1|Dancing in the Dark"
#    "a7f58467-a0b4-4d23-a7e0-037f30dc095f|Don'cha Go 'Way Mad"
#    "add13d9b-ed87-4dbf-8d31-1b74cb17644e|Everything I Love"
#    "099e7d1f-0ae6-4a8f-be10-0b5a313ec34c|Good Bait"
#    "f638f2c4-89f9-47e4-a85c-f53de157c987|I Concentrate on You"
    "32f3a71a-fa62-4a75-a734-0a237f80b156|I Didn't Know What Time It Was"
    "e57faa02-f057-40a5-ba1a-1e42e58c485e|It's a Sin to Tell a Lie"
    "311c231b-680f-41cb-9139-18de7625c395|Killer Joe"
    "2bebeeaf-d045-4b59-870d-44ee3c209a65|O Grande Amor"
    "76f77a03-c19b-45f4-a525-c28f6cedaf85|Once I Loved"
    "3c59c48a-b098-4373-82e1-19545265867d|Si tu vois ma mère"
    "e1212ef2-d7b0-419e-b3c3-2b4c3b122e74|Someone to Light Up My Life"
    "872d7739-5ea8-4852-bc8d-f752b1a4a5a2|Summertime"
    "4d98faa9-ab04-48fc-9da0-bdae7505d065|Sunday in New York"
    "ff73c933-8a8f-402b-a8b8-6eb4b36d08a1|There's No You"
    "8588a7f8-0343-4957-b413-c95efdf1bcd1|They Didn't Believe Me"
    "aaa7fd34-7c65-4d23-b54d-c8c7c6f951ed|We'll Meet Again"
    "aa542c35-26f1-4363-ae53-31d91f0e064a|Who Cares?"
)

count=0
total=${#songs[@]}

for entry in "${songs[@]}"; do
    song_id="${entry%%|*}"
    song_title="${entry#*|}"
    count=$((count + 1))

    echo ""
    echo "[$count/$total] Processing: $song_title"
    echo "----------------------------------------"

    python scripts/match_spotify_tracks.py --id "$song_id" --rematch-all
done

echo ""
echo "=========================================="
echo "Complete! Processed $total songs."
echo "=========================================="
