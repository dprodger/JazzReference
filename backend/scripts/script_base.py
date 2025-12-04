#!/usr/bin/env python3
"""
Script Base - Common infrastructure for CLI scripts

Provides a base class that handles:
- Path setup for imports from parent directory
- Logging configuration (stdout + file)
- Argument parsing with common options
- Header/summary printing with consistent formatting
- Exception handling and exit codes

Usage:
    from script_base import ScriptBase, run_script

    def main():
        script = ScriptBase(
            name="my_script",
            description="Does something useful",
            epilog="Examples:\\n  python my_script.py --name 'Test'"
        )

        # Add common argument groups as needed
        script.add_song_args()      # --name/--id for song selection
        script.add_dry_run_arg()    # --dry-run
        script.add_debug_arg()      # --debug
        script.add_force_refresh_arg()  # --force-refresh

        # Add script-specific arguments
        script.parser.add_argument('--limit', type=int, default=100)

        # Parse and get args
        args = script.parse_args()

        # Print header with active modes
        script.print_header({
            "DRY RUN": args.dry_run,
            "FORCE REFRESH": args.force_refresh,
        })

        # Do work...
        result = do_something(args)

        # Print summary
        script.print_summary(result['stats'])

        return result['success']

    if __name__ == "__main__":
        run_script(main)
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Callable, Optional

# Add parent directory to path for imports (do this immediately)
sys.path.insert(0, str(Path(__file__).parent.parent))


class ScriptBase:
    """Base class providing common CLI script infrastructure."""

    def __init__(
        self,
        name: str,
        description: str,
        epilog: str = "",
        log_dir: Optional[Path] = None
    ):
        """
        Initialize the script base.

        Args:
            name: Script name (used for log file naming)
            description: Script description for --help
            epilog: Additional help text (examples, etc.)
            log_dir: Directory for log files (default: scripts/log/)
        """
        self.name = name
        self.log_dir = log_dir or Path(__file__).parent / 'log'
        self.logger = self._setup_logging()
        self.parser = self._create_parser(description, epilog)
        self._song_args_group = None

    def _setup_logging(self) -> logging.Logger:
        """Configure logging with stdout and file handlers."""
        self.log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.log_dir / f'{self.name}.log')
            ]
        )
        return logging.getLogger(self.name)

    def _create_parser(self, description: str, epilog: str) -> argparse.ArgumentParser:
        """Create the argument parser."""
        return argparse.ArgumentParser(
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=epilog
        )

    # =========================================================================
    # Common Argument Groups
    # =========================================================================

    def add_song_args(self, required: bool = True) -> argparse.ArgumentParser:
        """
        Add mutually exclusive --name/--id arguments for song selection.

        Args:
            required: Whether one of --name or --id is required

        Returns:
            The mutually exclusive group (for adding more options if needed)
        """
        group = self.parser.add_mutually_exclusive_group(required=required)
        group.add_argument('--name', help='Song name')
        group.add_argument('--id', help='Song database ID')
        self._song_args_group = group
        return group

    def add_dry_run_arg(self):
        """Add --dry-run argument."""
        self.parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen without making changes'
        )

    def add_debug_arg(self):
        """Add --debug argument."""
        self.parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug logging'
        )

    def add_force_refresh_arg(self):
        """Add --force-refresh argument."""
        self.parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Bypass cache and fetch fresh data from APIs'
        )

    def add_limit_arg(self, default: int = 100):
        """Add --limit argument."""
        self.parser.add_argument(
            '--limit',
            type=int,
            default=default,
            help=f'Maximum number of items to process (default: {default})'
        )

    def add_common_args(self):
        """Add all common arguments (dry-run, debug, force-refresh)."""
        self.add_dry_run_arg()
        self.add_debug_arg()
        self.add_force_refresh_arg()

    # =========================================================================
    # Argument Parsing
    # =========================================================================

    def parse_args(self, args=None) -> argparse.Namespace:
        """
        Parse command line arguments and apply common settings.

        Args:
            args: Arguments to parse (default: sys.argv)

        Returns:
            Parsed arguments namespace
        """
        parsed = self.parser.parse_args(args)

        # Apply debug logging if requested
        if getattr(parsed, 'debug', False):
            logging.getLogger().setLevel(logging.DEBUG)
            self.logger.debug("Debug logging enabled")

        return parsed

    # =========================================================================
    # Output Formatting
    # =========================================================================

    def print_header(self, modes: dict = None, title: str = None):
        """
        Print a formatted header with optional mode indicators.

        Args:
            modes: Dict of mode_name -> is_active (e.g., {"DRY RUN": True})
            title: Custom title (default: script name formatted)
        """
        title = title or self.name.replace('_', ' ').title()

        self.logger.info("=" * 80)
        self.logger.info(title)
        self.logger.info("=" * 80)

        if modes:
            for mode_name, is_active in modes.items():
                if is_active:
                    self.logger.info(f"*** {mode_name} MODE ***")

        self.logger.info("")

    def print_summary(self, stats: dict, title: str = "SUMMARY"):
        """
        Print a formatted summary of operation statistics.

        Args:
            stats: Dict of stat_name -> value
            title: Summary section title
        """
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(title)
        self.logger.info("=" * 80)

        if stats:
            # Find max key length for alignment
            max_key_len = max(len(str(k)) for k in stats.keys())

            for key, value in stats.items():
                # Format key: replace underscores, title case
                display_key = key.replace('_', ' ').title()
                self.logger.info(f"{display_key:<{max_key_len + 5}} {value}")

        self.logger.info("=" * 80)

    def print_section(self, title: str, items: dict, indent: int = 2):
        """
        Print a subsection with indented items.

        Args:
            title: Section title
            items: Dict of label -> value
            indent: Number of spaces to indent items
        """
        self.logger.info(f"{title}:")
        prefix = " " * indent
        for label, value in items.items():
            self.logger.info(f"{prefix}{label}: {value}")

    # =========================================================================
    # Song Lookup Helper
    # =========================================================================

    def find_song(self, args: argparse.Namespace):
        """
        Find a song by name or ID from parsed arguments.

        Args:
            args: Parsed arguments with 'name' and 'id' attributes

        Returns:
            Song dict from database

        Raises:
            SystemExit: If song not found
        """
        from db_utils import find_song_by_name_or_id

        song = find_song_by_name_or_id(name=args.name, song_id=args.id)

        if song is None:
            identifier = args.name or args.id
            self.logger.error(f"Song not found: {identifier}")
            sys.exit(1)

        self.logger.info(f"Found song: {song['title']} (ID: {song['id']})")
        return song


def run_script(main_func: Callable[[], bool]):
    """
    Run a script's main function with standard exception handling.

    Args:
        main_func: Function that returns True on success, False on failure
    """
    try:
        success = main_func()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
