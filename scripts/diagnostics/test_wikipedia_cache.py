#!/usr/bin/env python3
"""
Wikipedia Search Cache Test Script
Demonstrates and tests the enhanced Wikipedia search caching functionality
"""

import sys
import argparse
import logging
import time
from pathlib import Path

# Add parent directory to path if needed
from wiki_utils import WikipediaSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/test_wikipedia_cache.log')
    ]
)
logger = logging.getLogger(__name__)


class WikipediaCacheTester:
    """Test Wikipedia search caching functionality"""
    
    def __init__(self, cache_dir='cache/wikipedia', force_refresh=False):
        """
        Initialize tester
        
        Args:
            cache_dir: Directory for cache storage
            force_refresh: If True, bypass cache
        """
        self.searcher = WikipediaSearcher(
            cache_dir=cache_dir,
            cache_days=7,
            force_refresh=force_refresh
        )
        self.stats = {
            'searches_performed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'pages_fetched': 0
        }
    
    def test_search_caching(self, performer_name):
        """
        Test search caching by performing the same search twice
        
        Args:
            performer_name: Name to search for
        """
        logger.info("="*80)
        logger.info(f"Testing Search Caching for: {performer_name}")
        logger.info("="*80)
        
        context = {
            'birth_date': None,
            'death_date': None,
            'sample_songs': []
        }
        
        # First search - should hit API
        logger.info("\n--- First Search (should fetch from API) ---")
        start_time = time.time()
        result1 = self.searcher.search_wikipedia(performer_name, context)
        time1 = time.time() - start_time
        
        logger.info(f"Result: {result1}")
        logger.info(f"Time taken: {time1:.2f} seconds")
        
        # Second search - should hit cache
        logger.info("\n--- Second Search (should use cache) ---")
        start_time = time.time()
        result2 = self.searcher.search_wikipedia(performer_name, context)
        time2 = time.time() - start_time
        
        logger.info(f"Result: {result2}")
        logger.info(f"Time taken: {time2:.2f} seconds")
        
        # Compare results
        logger.info("\n--- Comparison ---")
        logger.info(f"Results match: {result1 == result2}")
        logger.info(f"Speedup: {time1/time2:.2f}x faster")
        
        self.stats['searches_performed'] += 2
        if result1 == result2 and time2 < time1:
            self.stats['cache_hits'] += 1
            logger.info("✓ Cache working correctly!")
        else:
            logger.warning("⚠ Cache may not be working as expected")
    
    def test_multiple_performers(self, performers):
        """
        Test caching with multiple performers
        
        Args:
            performers: List of performer names
        """
        logger.info("="*80)
        logger.info("Testing Multiple Performers")
        logger.info("="*80)
        
        context = {
            'birth_date': None,
            'death_date': None,
            'sample_songs': []
        }
        
        for performer in performers:
            logger.info(f"\nSearching for: {performer}")
            result = self.searcher.search_wikipedia(performer, context)
            logger.info(f"Result: {result}")
            self.stats['searches_performed'] += 1
        
        # Now search again to test cache
        logger.info("\n--- Second pass (should use cache) ---")
        for performer in performers:
            logger.info(f"\nSearching for: {performer}")
            result = self.searcher.search_wikipedia(performer, context)
            logger.info(f"Result: {result}")
    
    def show_cache_stats(self):
        """Display cache statistics"""
        logger.info("")
        logger.info("="*80)
        logger.info("CACHE STATISTICS")
        logger.info("="*80)
        
        
        logger.info("")
        logger.info(f"Searches Performed: {self.stats['searches_performed']}")
        logger.info("="*80)
    
    def clear_cache(self, search_only=False):
        """Clear cache"""
        logger.info("")
        logger.info("="*80)
        if search_only:
            logger.info("CLEARING SEARCH CACHE ONLY")
        else:
            logger.info("CLEARING ALL CACHE")
        logger.info("="*80)
        
        self.searcher.clear_cache(search_only=search_only)
        logger.info("Cache cleared successfully")


def main():
    parser = argparse.ArgumentParser(
        description='Test Wikipedia search caching functionality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single performer
  python test_wikipedia_cache.py "Miles Davis"
  
  # Test with force refresh (bypass cache)
  python test_wikipedia_cache.py "Miles Davis" --force-refresh
  
  # Test multiple performers
  python test_wikipedia_cache.py --multi
  
  # Show cache stats
  python test_wikipedia_cache.py --stats
  
  # Clear cache
  python test_wikipedia_cache.py --clear-cache
  
  # Clear only search cache
  python test_wikipedia_cache.py --clear-search-cache
  
  # Enable debug logging
  python test_wikipedia_cache.py "Miles Davis" --debug
        """
    )
    
    parser.add_argument(
        'performer',
        nargs='?',
        help='Performer name to search for'
    )
    
    parser.add_argument(
        '--multi',
        action='store_true',
        help='Test with multiple well-known performers'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show cache statistics'
    )
    
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear all cache'
    )
    
    parser.add_argument(
        '--clear-search-cache',
        action='store_true',
        help='Clear only search cache (keep page cache)'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh, bypass cache'
    )
    
    parser.add_argument(
        '--cache-dir',
        default='cache/wikipedia',
        help='Cache directory (default: cache/wikipedia)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create log directory if needed
    Path('log').mkdir(exist_ok=True)
    
    # Create tester
    tester = WikipediaCacheTester(
        cache_dir=args.cache_dir,
        force_refresh=args.force_refresh
    )
    
    try:
        # Handle different modes
        if args.clear_cache:
            tester.clear_cache(search_only=False)
            tester.show_cache_stats()
            
        elif args.clear_search_cache:
            tester.clear_cache(search_only=True)
            tester.show_cache_stats()
            
        elif args.stats:
            tester.show_cache_stats()
            
        elif args.multi:
            # Test with multiple performers
            performers = [
                "Miles Davis",
                "John Coltrane",
                "Duke Ellington",
                "Charlie Parker"
            ]
            tester.test_multiple_performers(performers)
            tester.show_cache_stats()
            
        elif args.performer:
            # Test single performer
            tester.test_search_caching(args.performer)
            tester.show_cache_stats()
            
        else:
            parser.print_help()
            return
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()