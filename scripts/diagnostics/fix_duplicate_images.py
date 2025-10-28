#!/usr/bin/env python3
"""
Database Migration: Fix Duplicate Images and Add Constraints
Handles duplicate image URLs in the images table and ensures proper constraints

The real problem: Multiple rows in the images table with the same URL.
Solution: Keep one image per URL, redirect all artist_images references to it, delete the rest.

Usage:
    python fix_duplicate_images.py
    python fix_duplicate_images.py --dry-run
    python fix_duplicate_images.py --remove-duplicates
"""

import sys
import argparse
import logging
from typing import List, Dict, Any

from db_utils import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_for_duplicate_urls() -> List[Dict[str, Any]]:
    """
    Check for duplicate URLs in the images table.
    
    Returns:
        List of dicts with url, count, and image_ids for duplicates
    """
    logger.info("Checking for duplicate image URLs in images table...")
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT url, COUNT(*) as count, ARRAY_AGG(id ORDER BY created_at) as image_ids
                FROM images
                GROUP BY url
                HAVING COUNT(*) > 1
                ORDER BY count DESC, url
            """
            cur.execute(query)
            duplicates = cur.fetchall()
    
    return duplicates


def show_duplicate_details(duplicates: List[Dict[str, Any]]) -> None:
    """
    Show detailed information about duplicate image URLs.
    
    Args:
        duplicates: List of duplicate records
    """
    if not duplicates:
        logger.info("✓ No duplicate image URLs found")
        return
    
    logger.warning(f"Found {len(duplicates)} URLs with duplicate entries:")
    logger.warning("")
    
    total_duplicate_rows = sum(dup['count'] - 1 for dup in duplicates)
    logger.warning(f"Total duplicate rows that will be removed: {total_duplicate_rows}")
    logger.warning("")
    
    # Show details for first 10 for readability
    display_count = min(10, len(duplicates))
    logger.warning(f"Showing details for first {display_count} of {len(duplicates)} duplicate URLs:")
    logger.warning("")
    
    for dup in duplicates[:display_count]:
        url = dup['url']
        count = dup['count']
        image_ids = dup['image_ids']
        
        logger.warning(f"  URL: {url}")
        logger.warning(f"  Duplicate count: {count}")
        logger.warning(f"  Image IDs: {image_ids}")
        
        # Show which performers are affected
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(image_ids))
                cur.execute(f"""
                    SELECT ai.image_id, p.name as performer_name
                    FROM artist_images ai
                    JOIN performers p ON ai.performer_id = p.id
                    WHERE ai.image_id IN ({placeholders})
                    ORDER BY ai.image_id
                """, image_ids)
                
                affected = cur.fetchall()
                if affected:
                    logger.warning(f"  Affected performers:")
                    for aff in affected:
                        logger.warning(f"    - {aff['performer_name']} (using image_id: {aff['image_id']})")
                
        logger.warning("")
    
    if len(duplicates) > display_count:
        logger.warning(f"  ... and {len(duplicates) - display_count} more duplicate URLs")
        logger.warning("")
        logger.warning(f"NOTE: Only showing first {display_count} for readability.")
        logger.warning(f"      ALL {len(duplicates)} duplicate URLs will be processed during consolidation.")
        logger.warning("")


def consolidate_duplicate_images(dry_run: bool = False) -> int:
    """
    Consolidate duplicate image URLs by:
    1. Keeping the oldest image record for each URL
    2. Updating all artist_images references to point to the kept image
    3. Deleting the duplicate image records
    
    Args:
        dry_run: If True, show what would be done without making changes
    
    Returns:
        Number of duplicate image records removed
    """
    duplicates = check_for_duplicate_urls()
    
    if not duplicates:
        logger.info("✓ No duplicate URLs to consolidate")
        return 0
    
    total_duplicate_rows = sum(dup['count'] - 1 for dup in duplicates)
    logger.info(f"Consolidating {len(duplicates)} duplicate URLs ({total_duplicate_rows} duplicate rows to remove)...")
    logger.info("")
    total_removed = 0
    
    for idx, dup in enumerate(duplicates, 1):
        logger.info(f"Processing {idx}/{len(duplicates)}...")
        url = dup['url']
        count = dup['count']
        image_ids = dup['image_ids']
        
        # Keep the first (oldest) one, remove the rest
        keep_id = image_ids[0]
        remove_ids = image_ids[1:]
        
        logger.info(f"Processing URL: {url[:80]}...")
        logger.info(f"  Keeping image_id: {keep_id}")
        logger.info(f"  Removing {len(remove_ids)} duplicate(s): {remove_ids}")
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would consolidate artist_images references:")
            logger.info(f"    - Update references where performer doesn't have kept image")
            logger.info(f"    - Delete references where performer already has kept image")
            logger.info(f"  [DRY RUN] Would delete {len(remove_ids)} duplicate image record(s)")
            total_removed += len(remove_ids)
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # Step 1: For each duplicate image, handle artist_images references
                        # Strategy: Update only if it won't create a duplicate, otherwise delete
                        if remove_ids:
                            updated_count = 0
                            deleted_ref_count = 0
                            
                            for remove_id in remove_ids:
                                # Get all performers linked to this duplicate image
                                cur.execute("""
                                    SELECT performer_id
                                    FROM artist_images
                                    WHERE image_id = %s
                                """, (remove_id,))
                                
                                refs = cur.fetchall()
                                
                                for ref in refs:
                                    performer_id = ref['performer_id']
                                    
                                    # Check if this performer already has the kept image
                                    cur.execute("""
                                        SELECT 1 FROM artist_images
                                        WHERE performer_id = %s AND image_id = %s
                                    """, (performer_id, keep_id))
                                    
                                    if cur.fetchone():
                                        # Performer already has the kept image, delete this duplicate reference
                                        cur.execute("""
                                            DELETE FROM artist_images 
                                            WHERE performer_id = %s AND image_id = %s
                                        """, (performer_id, remove_id))
                                        deleted_ref_count += 1
                                    else:
                                        # Performer doesn't have the kept image, update to use it
                                        cur.execute("""
                                            UPDATE artist_images
                                            SET image_id = %s
                                            WHERE performer_id = %s AND image_id = %s
                                        """, (keep_id, performer_id, remove_id))
                                        updated_count += 1
                            
                            if updated_count > 0:
                                logger.info(f"  ✓ Updated {updated_count} artist_images reference(s) to use {keep_id}")
                            if deleted_ref_count > 0:
                                logger.info(f"  ✓ Deleted {deleted_ref_count} duplicate artist_images reference(s)")
                        
                        # Step 2: Delete the duplicate image records
                        if remove_ids:
                            placeholders = ','.join(['%s'] * len(remove_ids))
                            delete_query = f"DELETE FROM images WHERE id IN ({placeholders})"
                            cur.execute(delete_query, remove_ids)
                            deleted_count = cur.rowcount
                            logger.info(f"  ✓ Deleted {deleted_count} duplicate image record(s)")
                            total_removed += deleted_count
                
            except Exception as e:
                logger.error(f"  ✗ Error consolidating URL {url[:80]}: {e}")
                if not dry_run:
                    raise
    
    logger.info("")
    if not dry_run:
        logger.info(f"✓ Processed all {len(duplicates)} duplicate URLs")
        logger.info(f"✓ Removed {total_removed} total duplicate image records")
    else:
        logger.info(f"[DRY RUN] Would process all {len(duplicates)} duplicate URLs")
        logger.info(f"[DRY RUN] Would remove {total_removed} total duplicate image records")
    
    return total_removed


def check_images_url_unique_constraint() -> bool:
    """
    Check if unique constraint exists on images.url.
    
    Returns:
        True if constraint exists, False otherwise
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'images'
                  AND constraint_type = 'UNIQUE'
                  AND constraint_name = 'images_url_unique'
            """
            cur.execute(query)
            result = cur.fetchone()
            return result is not None


def check_artist_images_unique_constraint() -> bool:
    """
    Check if unique constraint exists on artist_images (performer_id, image_id).
    
    Returns:
        True if constraint exists, False otherwise
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'artist_images'
                  AND constraint_type = 'UNIQUE'
                  AND constraint_name = 'artist_images_performer_image_unique'
            """
            cur.execute(query)
            result = cur.fetchone()
            return result is not None


def add_constraints(dry_run: bool = False) -> bool:
    """
    Add unique constraints to prevent future duplicates:
    1. UNIQUE constraint on images.url
    2. UNIQUE constraint on artist_images (performer_id, image_id)
    
    Args:
        dry_run: If True, show what would be done without making changes
    
    Returns:
        True if successful, False otherwise
    """
    success = True
    
    # Check and add images.url unique constraint
    if check_images_url_unique_constraint():
        logger.info("✓ Unique constraint already exists on images.url")
    else:
        if dry_run:
            logger.info("[DRY RUN] Would add unique constraint: images_url_unique")
            logger.info("[DRY RUN] Constraint: UNIQUE (url)")
        else:
            try:
                logger.info("Adding unique constraint to images.url...")
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            ALTER TABLE images
                            ADD CONSTRAINT images_url_unique
                            UNIQUE (url)
                        """)
                logger.info("✓ Successfully added unique constraint: images_url_unique")
            except Exception as e:
                logger.error(f"✗ Error adding images.url constraint: {e}")
                success = False
    
    # Check and add artist_images (performer_id, image_id) unique constraint
    if check_artist_images_unique_constraint():
        logger.info("✓ Unique constraint already exists on artist_images (performer_id, image_id)")
    else:
        if dry_run:
            logger.info("[DRY RUN] Would add unique constraint: artist_images_performer_image_unique")
            logger.info("[DRY RUN] Constraint: UNIQUE (performer_id, image_id)")
        else:
            try:
                logger.info("Adding unique constraint to artist_images (performer_id, image_id)...")
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            ALTER TABLE artist_images
                            ADD CONSTRAINT artist_images_performer_image_unique
                            UNIQUE (performer_id, image_id)
                        """)
                logger.info("✓ Successfully added unique constraint: artist_images_performer_image_unique")
            except Exception as e:
                logger.error(f"✗ Error adding artist_images constraint: {e}")
                success = False
    
    return success


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description='Fix duplicate image URLs and add constraints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check for duplicates (dry run)
    python fix_duplicate_images.py --dry-run
    
    # Remove duplicates and add constraints
    python fix_duplicate_images.py --remove-duplicates
    
    # Just add constraints (if no duplicates exist)
    python fix_duplicate_images.py
    
How it works:
    1. Finds all URLs that appear multiple times in the images table
    2. For each duplicate URL:
       - Keeps the oldest image record
       - Updates all artist_images references to point to the kept image
       - Deletes duplicate artist_images entries (same performer + image)
       - Deletes the duplicate image records
    3. Adds UNIQUE constraints to prevent future duplicates:
       - images.url must be unique
       - artist_images (performer_id, image_id) must be unique
        """
    )
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--remove-duplicates', action='store_true',
                       help='Remove duplicate image URLs before adding constraints')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("Database Migration: Fix Duplicate Images")
    logger.info("="*80)
    logger.info("")
    
    # Step 1: Check for duplicate URLs
    duplicates = check_for_duplicate_urls()
    
    if duplicates:
        logger.warning(f"⚠ Found {len(duplicates)} URLs with duplicate entries")
        show_duplicate_details(duplicates)
        
        if not args.remove_duplicates:
            logger.error("")
            logger.error("Cannot add unique constraints while duplicates exist.")
            logger.error("Run with --remove-duplicates to consolidate duplicates first.")
            logger.error("")
            logger.error("What will happen:")
            logger.error("  1. Keep the oldest image record for each URL")
            logger.error("  2. Update all artist_images to reference the kept image")
            logger.error("  3. Delete duplicate artist_images entries")
            logger.error("  4. Delete duplicate image records")
            logger.error("")
            sys.exit(1)
        
        # Consolidate duplicates
        logger.info("")
        logger.info("Consolidating duplicate images...")
        removed = consolidate_duplicate_images(dry_run=args.dry_run)
        
        if args.dry_run:
            logger.info(f"[DRY RUN] Would remove {removed} duplicate image record(s)")
        else:
            logger.info(f"✓ Removed {removed} duplicate image record(s)")
        
        # Check again
        if not args.dry_run:
            remaining_duplicates = check_for_duplicate_urls()
            if remaining_duplicates:
                logger.error("⚠ Still have duplicates after consolidation. Please investigate.")
                show_duplicate_details(remaining_duplicates)
                sys.exit(1)
            else:
                logger.info("✓ All duplicates successfully consolidated")
    
    # Step 2: Add unique constraints
    logger.info("")
    logger.info("Adding unique constraints...")
    success = add_constraints(dry_run=args.dry_run)
    
    if success:
        logger.info("")
        logger.info("="*80)
        if args.dry_run:
            logger.info("✓ Migration complete (DRY RUN)")
        else:
            logger.info("✓ Migration complete!")
        logger.info("="*80)
        logger.info("")
        logger.info("Constraints added:")
        logger.info("  1. images.url UNIQUE - prevents duplicate URLs")
        logger.info("  2. artist_images (performer_id, image_id) UNIQUE - prevents duplicate links")
        logger.info("")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("="*80)
        logger.error("✗ Migration failed")
        logger.error("="*80)
        sys.exit(1)


if __name__ == '__main__':
    main()
