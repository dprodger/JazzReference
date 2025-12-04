#!/usr/bin/env python3
"""
Cover Art Archive Image Importer - Command Line Interface

Fetches cover art from the Cover Art Archive (CAA) for releases and imports
them into the release_imagery table.
"""

from script_base import ScriptBase, run_script
from caa_release_importer import CAAImageImporter


def main() -> bool:
    script = ScriptBase(
        name="import_caa_images",
        description="Import cover art from Cover Art Archive for jazz releases",
        epilog="""
Examples:
  # Import cover art for all releases of a song (by name)
  python import_caa_images.py --name "Take Five"

  # Import cover art for all releases of a song (by ID)
  python import_caa_images.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890

  # Import cover art for ALL unchecked releases (batch mode)
  python import_caa_images.py --all

  # Dry run to see what would be imported
  python import_caa_images.py --name "Blue in Green" --dry-run

  # Enable debug logging
  python import_caa_images.py --name "Autumn Leaves" --debug

  # Force refresh from CAA API (bypass cache)
  python import_caa_images.py --name "Autumn Leaves" --force-refresh

  # Limit number of releases to process
  python import_caa_images.py --all --limit 50

What this script does:
  1. Finds releases for a song (or all unchecked releases in batch mode)
  2. Queries the Cover Art Archive for each release
  3. Downloads image metadata (URLs for different sizes)
  4. Creates release_imagery records in the database
  5. Marks releases as checked (cover_art_checked_at)

Notes:
  - By default, releases that have already been checked are SKIPPED
  - Use --force-refresh to re-check already processed releases
  - The CAA API has no rate limiting, but we use conservative delays
  - Results are cached locally to avoid repeated API calls
  - Only Front and Back cover types are imported
  - Releases without MusicBrainz IDs are skipped
        """
    )

    # Song selection with --all as additional option
    group = script.parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--name', help='Song name to find releases for')
    group.add_argument('--id', help='Song database ID (UUID)')
    group.add_argument('--all', action='store_true',
                       help='Process all releases that have not been checked for cover art')

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_force_refresh_arg()
    script.add_limit_arg(default=500)

    args = script.parse_args()

    batch_mode = args.all

    # Print header
    script.print_header({
        "DRY RUN": args.dry_run,
        "FORCE REFRESH": args.force_refresh,
        "BATCH": batch_mode,
    })

    # Create importer
    importer = CAAImageImporter(
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        logger=script.logger
    )

    # Run import
    if batch_mode:
        script.logger.info(f"Processing unchecked releases (limit: {args.limit})...")
        result = importer.import_all_unchecked(limit=args.limit)
    else:
        song_identifier = args.name or args.id
        script.logger.info(f"Finding song: {song_identifier}")
        result = importer.import_for_song(song_identifier, limit=args.limit)

    # Print summary
    if result['success']:
        stats = result['stats']

        if not batch_mode and 'song' in result:
            song = result['song']
            script.print_section("Song", {
                "Title": song['title'],
                "Composer": song.get('composer', 'Unknown'),
            })

        if result.get('message'):
            script.logger.info(f"Note: {result['message']}")
            script.logger.info("")

        script.print_section("Releases", {
            "Processed": stats['releases_processed'],
            "With art": stats['releases_with_art'],
            "No art": stats['releases_no_art'],
        })

        script.print_section("Images", {
            "Created": stats['images_created'],
            "Updated": stats['images_updated'],
            "Already exist": stats['images_existing'],
        })

        script.print_section("API Performance", {
            "API calls": stats['api_calls'],
            "Cache hits": stats['cache_hits'],
        })

        script.logger.info(f"Errors: {stats['errors']}")
        script.logger.info("=" * 80)
        script.logger.info("Import completed successfully")
    else:
        script.logger.error(f"Import failed: {result.get('error', 'Unknown error')}")

    return result['success']


if __name__ == "__main__":
    run_script(main)
