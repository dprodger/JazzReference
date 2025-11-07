#!/usr/bin/env python3
"""
Batch Jazz Song Research
Process multiple songs from a file and generate SQL inserts
"""

import sys
import json
import time
import os
from pathlib import Path

# Import the main researcher
# Make sure jazz_song_research.py is in the same directory
try:
    from jazz_song_research import JazzSongResearcher
except ImportError:
    print("Error: jazz_song_research.py must be in the same directory")
    sys.exit(1)

def batch_research(song_list_file, output_dir='output', delay=2):
    """
    Research multiple songs and save results
    
    Args:
        song_list_file: Path to file with song names (one per line)
        output_dir: Directory to save output files
        delay: Seconds to wait between requests
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    researcher = JazzSongResearcher()
    results = []
    sql_statements = []
    
    # Read song list
    with open(song_list_file, 'r') as f:
        songs = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"Found {len(songs)} songs to research")
    print("=" * 60)
    
    # Process each song
    for i, song in enumerate(songs, 1):
        print(f"\n[{i}/{len(songs)}] Researching: {song}")
        print("-" * 60)
        
        try:
            # Research the song
            result = researcher.research_song(song)
            results.append(result)
            
            # Save individual JSON
            safe_filename = song.replace(' ', '_').replace('/', '_').lower()
            json_file = f'{output_dir}/{safe_filename}.json'
            with open(json_file, 'w') as out:
                json.dump(result, out, indent=2)
            print(f"✓ Saved JSON: {json_file}")
            
            # Generate SQL
            sql = researcher.generate_sql_insert(result['structured_output'])
            sql_statements.append(sql)
            
            # Save individual SQL
            sql_file = f'{output_dir}/{safe_filename}.sql'
            with open(sql_file, 'w') as out:
                out.write(sql)
            print(f"✓ Saved SQL: {sql_file}")
            
            # Be respectful - wait between requests
            if i < len(songs):
                print(f"Waiting {delay} seconds before next request...")
                time.sleep(delay)
            
        except Exception as e:
            print(f"✗ Error researching '{song}': {e}")
            # Continue with next song
    
    # Save combined results
    print("\n" + "=" * 60)
    print("Saving combined results...")
    
    # Combined JSON
    combined_json = f'{output_dir}/all_songs.json'
    with open(combined_json, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Saved combined JSON: {combined_json}")
    
    # Combined SQL
    combined_sql = f'{output_dir}/all_songs.sql'
    with open(combined_sql, 'w') as f:
        f.write("-- Batch Insert for Jazz Songs\n")
        f.write(f"-- Generated from: {song_list_file}\n")
        f.write(f"-- Total songs: {len(results)}\n\n")
        f.write("BEGIN;\n\n")
        f.write('\n'.join(sql_statements))
        f.write("\nCOMMIT;\n")
    print(f"✓ Saved combined SQL: {combined_sql}")
    
    # Generate summary
    summary = {
        'total_songs': len(songs),
        'successful': len(results),
        'failed': len(songs) - len(results),
        'songs_with_wikipedia': sum(1 for r in results if 'wikipedia' in r.get('sources', {})),
        'songs_with_composer': sum(1 for r in results if r.get('extracted_data', {}).get('composer')),
        'songs_with_year': sum(1 for r in results if r.get('extracted_data', {}).get('year')),
    }
    
    summary_file = f'{output_dir}/summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary: {summary_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total songs processed: {summary['successful']}/{summary['total_songs']}")
    print(f"Songs with Wikipedia: {summary['songs_with_wikipedia']}")
    print(f"Songs with composer info: {summary['songs_with_composer']}")
    print(f"Songs with year info: {summary['songs_with_year']}")
    
    if summary['failed'] > 0:
        print(f"\n⚠ Warning: {summary['failed']} songs failed")
    
    print(f"\n✓ All results saved to: {output_dir}/")
    print(f"✓ Ready to import SQL: psql jazz_reference < {combined_sql}")

def main():
    if len(sys.argv) < 2:
        print("Batch Jazz Song Research")
        print("=" * 60)
        print("\nUsage:")
        print("  python batch_research.py <song_list_file> [output_dir] [delay]")
        print("\nArguments:")
        print("  song_list_file  - Text file with song names (one per line)")
        print("  output_dir      - Directory for output files (default: 'output')")
        print("  delay          - Seconds between requests (default: 2)")
        print("\nExample:")
        print("  python batch_research.py songs_to_research.txt output 3")
        print("\nSong list file format:")
        print("  Take Five")
        print("  Blue Bossa")
        print("  # Comments start with #")
        print("  Maiden Voyage")
        sys.exit(1)
    
    song_list_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'output'
    delay = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    
    if not os.path.exists(song_list_file):
        print(f"Error: File not found: {song_list_file}")
        sys.exit(1)
    
    batch_research(song_list_file, output_dir, delay)

if __name__ == "__main__":
    main()