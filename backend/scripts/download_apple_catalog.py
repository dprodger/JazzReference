#!/usr/bin/env python3
"""
Apple Music Catalog Downloader

Downloads the Apple Music catalog via the Feed API for local matching.
This provides bulk access to Apple Music's catalog without rate limiting.

Prerequisites:
  1. Apple Developer Program membership
  2. Create a Media ID in Apple Developer portal
  3. Generate a private key (.p8 file)
  4. Set environment variables:
     - APPLE_MEDIA_ID
     - APPLE_PRIVATE_KEY_PATH
     - APPLE_KEY_ID
     - APPLE_TEAM_ID

Usage:
  # Download all feeds (albums, artists, songs)
  python download_apple_catalog.py --all

  # Download specific feed
  python download_apple_catalog.py --feed albums
  python download_apple_catalog.py --feed songs

  # Show catalog statistics
  python download_apple_catalog.py --stats

  # Check configuration
  python download_apple_catalog.py --check-config
"""

import sys
import os
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file from backend directory
from dotenv import load_dotenv
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, '.env'))

from script_base import ScriptBase, run_script
from apple_music_feed import (
    AppleMusicFeedClient,
    AppleMusicCatalog,
    is_feed_configured,
    FEEDS
)


def main() -> bool:
    script = ScriptBase(
        name="download_apple_catalog",
        description="Download Apple Music catalog via Feed API",
        epilog="""
Prerequisites:
  1. Apple Developer Program membership ($99/year)
  2. Create a Media ID in App Store Connect > Users and Access > Integrations
  3. Generate a private key and download the .p8 file
  4. Set the following environment variables in your .env file:
     - APPLE_MEDIA_ID: Your Media ID
     - APPLE_PRIVATE_KEY_PATH: Path to your .p8 file
     - APPLE_KEY_ID: The Key ID shown in App Store Connect
     - APPLE_TEAM_ID: Your Team ID (from Account > Membership)

Examples:
  # Check if configuration is valid
  python download_apple_catalog.py --check-config

  # Download albums catalog
  python download_apple_catalog.py --feed albums

  # Download all catalogs (warning: ~50GB+ total)
  python download_apple_catalog.py --all

  # Show statistics about downloaded catalogs
  python download_apple_catalog.py --stats
        """
    )

    script.parser.add_argument(
        '--feed',
        choices=list(FEEDS.keys()),
        help='Which feed to download (albums, artists, songs)'
    )

    script.parser.add_argument(
        '--all',
        action='store_true',
        help='Download all feeds (warning: large download)'
    )

    script.parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics about downloaded catalogs'
    )

    script.parser.add_argument(
        '--check-config',
        action='store_true',
        help='Check if Apple Music Feed is configured correctly'
    )

    script.parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Number of parallel download threads (default: 4)'
    )

    script.parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip checksum verification (faster but risky)'
    )

    script.add_debug_arg()

    args = script.parse_args()

    # Check configuration
    if args.check_config:
        script.logger.info("Checking Apple Music Feed configuration...")

        env_vars = [
            ('APPLE_MEDIA_ID', os.environ.get('APPLE_MEDIA_ID')),
            ('APPLE_PRIVATE_KEY_PATH', os.environ.get('APPLE_PRIVATE_KEY_PATH')),
            ('APPLE_KEY_ID', os.environ.get('APPLE_KEY_ID')),
            ('APPLE_TEAM_ID', os.environ.get('APPLE_TEAM_ID')),
        ]

        all_set = True
        for name, value in env_vars:
            if value:
                # Mask sensitive values
                if 'KEY' in name or 'ID' in name:
                    display = value[:4] + '...' + value[-4:] if len(value) > 8 else '****'
                else:
                    display = value
                script.logger.info(f"  ✓ {name}: {display}")
            else:
                script.logger.error(f"  ✗ {name}: NOT SET")
                all_set = False

        # Check private key file exists
        key_path = os.environ.get('APPLE_PRIVATE_KEY_PATH')
        if key_path:
            if os.path.exists(key_path):
                script.logger.info(f"  ✓ Private key file exists")
            else:
                script.logger.error(f"  ✗ Private key file not found: {key_path}")
                all_set = False

        if all_set:
            script.logger.info("\n✓ Configuration looks valid!")
            script.logger.info("  Try: python download_apple_catalog.py --feed albums")
        else:
            script.logger.error("\n✗ Configuration incomplete. See --help for setup instructions.")

        return all_set

    # Show stats
    if args.stats:
        script.logger.info("Apple Music Catalog Statistics")
        script.logger.info("=" * 40)

        try:
            catalog = AppleMusicCatalog(logger=script.logger)
            stats = catalog.get_catalog_stats()

            for feed_name, feed_stats in stats.items():
                if feed_stats:
                    script.logger.info(f"\n{feed_name.upper()}:")
                    for key, value in feed_stats.items():
                        if isinstance(value, int):
                            script.logger.info(f"  {key}: {value:,}")
                        else:
                            script.logger.info(f"  {key}: {value}")
                else:
                    script.logger.info(f"\n{feed_name.upper()}: Not downloaded")

            return True
        except FileNotFoundError as e:
            script.logger.info("No catalog data downloaded yet.")
            script.logger.info("Run with --feed or --all to download.")
            return True

    # Download feeds
    if not args.feed and not args.all:
        script.parser.print_help()
        return True

    if not is_feed_configured():
        script.logger.error("Apple Music Feed is not configured.")
        script.logger.error("Run with --check-config to see what's missing.")
        return False

    feeds_to_download = list(FEEDS.keys()) if args.all else [args.feed]

    script.print_header({
        "FEEDS": ", ".join(feeds_to_download),
        "WORKERS": args.max_workers,
        "VERIFY CHECKSUMS": not args.no_verify,
    })

    client = AppleMusicFeedClient(logger=script.logger)

    success = True
    for feed_name in feeds_to_download:
        script.logger.info(f"\n{'='*60}")
        script.logger.info(f"Downloading {feed_name.upper()} catalog...")
        script.logger.info(f"{'='*60}")

        try:
            output_dir = client.download_feed(
                feed_name,
                max_workers=args.max_workers,
                verify_checksum=not args.no_verify
            )
            script.logger.info(f"✓ {feed_name} catalog saved to: {output_dir}")
        except Exception as e:
            script.logger.error(f"✗ Failed to download {feed_name}: {e}")
            success = False

    if success:
        script.logger.info("\n✓ All catalogs downloaded successfully!")
        script.logger.info("You can now use the Apple Music matcher with local data.")
    else:
        script.logger.error("\n✗ Some downloads failed. Check errors above.")

    return success


if __name__ == "__main__":
    run_script(main)
