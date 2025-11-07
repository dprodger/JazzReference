#!/usr/bin/env python3
"""
MusicBrainz Search Diagnostic
Tests different search strategies to find why an artist isn't found
"""

import requests
import json
import time
import sys

def search_musicbrainz(query_string, description):
    """Search MusicBrainz with a specific query"""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"Query: {query_string}")
    print('='*80)
    
    url = "https://musicbrainz.org/ws/2/artist/"
    params = {
        'query': query_string,
        'fmt': 'json',
        'limit': 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        time.sleep(1.1)  # MusicBrainz rate limiting
        
        print(f"Status: {response.status_code}")
        print(f"Response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            data = response.json()
            artists = data.get('artists', [])
            count = data.get('count', 0)
            
            print(f"Results found: {count}")
            
            if artists:
                print(f"\nTop {len(artists)} results:")
                for i, artist in enumerate(artists, 1):
                    name = artist.get('name', 'Unknown')
                    mbid = artist.get('id', 'Unknown')
                    score = artist.get('score', 0)
                    tags = [tag['name'] for tag in artist.get('tags', [])[:3]]
                    
                    print(f"\n  {i}. {name}")
                    print(f"     MBID: {mbid}")
                    print(f"     Score: {score}")
                    print(f"     Tags: {', '.join(tags) if tags else 'None'}")
                    
                    # Show aliases if any
                    if 'aliases' in artist and artist['aliases']:
                        aliases = [alias['name'] for alias in artist['aliases'][:3]]
                        print(f"     Aliases: {', '.join(aliases)}")
            else:
                print("\n  No results found")
                
        return response.json() if response.status_code == 200 else None
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    artist_name = "Deep Blue Organ Trio"
    
    print("="*80)
    print(f"MUSICBRAINZ SEARCH DIAGNOSTIC FOR: {artist_name}")
    print("="*80)
    
    # Test 1: Current query (strict, with jazz tag requirement)
    search_musicbrainz(
        f'artist:"{artist_name}" AND tag:jazz',
        "Current query (strict name match + jazz tag required)"
    )
    
    # Test 2: Without tag requirement
    search_musicbrainz(
        f'artist:"{artist_name}"',
        "Without tag requirement (strict name match only)"
    )
    
    # Test 3: Fuzzy name search without quotes
    search_musicbrainz(
        f'artist:{artist_name}',
        "Fuzzy name search (no quotes, no tag requirement)"
    )
    
    # Test 4: Just the name (very loose)
    search_musicbrainz(
        artist_name,
        "Loose search (just the name)"
    )
    
    # Test 5: Search by type=group if it's a band
    search_musicbrainz(
        f'{artist_name} AND type:group',
        "Search as a group/band"
    )
    
    # Test 6: Alternative spellings/formats
    search_musicbrainz(
        'Deep Blue Organ',
        "Partial name search"
    )
    
    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    print("\nAnalysis:")
    print("- If Test 1 returns 0 results but Test 2+ return results:")
    print("  → The artist exists but doesn't have the 'jazz' tag")
    print("  → Solution: Remove the 'AND tag:jazz' requirement from the query")
    print()
    print("- If Test 2 returns 0 results but Test 3+ return results:")
    print("  → The exact quoted name doesn't match MusicBrainz")
    print("  → Solution: Use fuzzy matching without quotes")
    print()
    print("- If all tests return 0 results:")
    print("  → The artist may not exist in MusicBrainz")
    print("  → You may need to add it manually or skip MusicBrainz for this artist")
    print()
    print("- Check the 'Score' values - higher scores indicate better matches")
    print("  → Scores > 90 are usually good matches")
    print("  → Scores < 70 might be false positives")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)