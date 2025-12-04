#!/usr/bin/env python3
"""
MusicBrainz Release Importer - Command Line Interface

Fetches recordings and releases for songs with MusicBrainz IDs and imports them
into the database. Creates recordings, releases, and links performers to recordings.
"""

from script_base import ScriptBase, run_script
from mb_release_importer import MBReleaseImporter


def main() -> bool:
    # Set up script with arguments
    script = ScriptBase(
        name="import_mb_releases",
        description="Import MusicBrainz recordings and releases for a jazz song",
        epilog="""
Examples:
  # Import by song name
  python import_mb_releases.py --name "Take Five"

  # Import by song ID
  python import_mb_releases.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890

  # Dry run to see what would be imported
  python import_mb_releases.py --name "Blue in Green" --dry-run

  # Enable debug logging
  python import_mb_releases.py --name "Autumn Leaves" --debug

  # Force refresh from MusicBrainz API (bypass cache)
  python import_mb_releases.py --name "Autumn Leaves" --force-refresh

  # Limit recordings to process
  python import_mb_releases.py --name "Body and Soul" --limit 10

What this script does:
  1. Finds the song by name or ID
  2. Fetches recordings from MusicBrainz (via the song's MusicBrainz Work ID)
  3. For each recording:
     - Creates the recording if it doesn't exist
     - Adds performers to the RECORDING (aggregated from all releases)
     - Fetches all releases containing that recording
     - Creates releases if they don't exist
     - Links recordings to releases
     - Adds release-specific credits (producers, engineers) to releases
        """
    )

    # Add arguments
    script.add_song_args()
    script.add_common_args()
    script.add_limit_arg(default=100)

    # Parse arguments
    args = script.parse_args()

    # Print header
    script.print_header({
        "DRY RUN": args.dry_run,
        "FORCE REFRESH": args.force_refresh,
    })

    # Find the song
    song = script.find_song(args)

    # Create importer and run
    importer = MBReleaseImporter(
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        logger=script.logger
    )

    result = importer.import_releases(song['id'], limit=args.limit)

    # Print summary
    if result['success']:
        script.print_section("Song", {
            "Title": result['song']['title'],
            "Composer": result['song']['composer'],
        })

        stats = result['stats']
        script.print_section("Recordings", {
            "Found": stats['recordings_found'],
            "Created": stats['recordings_created'],
            "Existing": stats['recordings_existing'],
        })

        release_stats = {
            "Found (new)": stats['releases_found'],
            "Created": stats['releases_created'],
            "Already exist": stats['releases_existing'],
        }
        if stats.get('releases_skipped_api', 0) > 0:
            release_stats["API calls skipped"] = stats['releases_skipped_api']
        script.print_section("Releases", release_stats)

        script.print_section("Performers", {
            "Added to recordings": stats['performers_added_to_recordings'],
            "Release credits": stats['release_credits_linked'],
        })

        script.logger.info(f"Links created: {stats['links_created']}")
        script.logger.info(f"Errors: {stats['errors']}")
        script.logger.info("=" * 80)
        script.logger.info("Import completed successfully")
    else:
        script.logger.error(f"Import failed: {result.get('error', 'Unknown error')}")

    return result['success']


if __name__ == "__main__":
    run_script(main)
