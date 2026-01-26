"""
HTML Regeneration Module for RealAgent Dashboard
=================================================

This module provides HTML regeneration functionality for the dashboard system.
It integrates with the universal builder system to regenerate listing HTML files
after edits are made through the dashboard interface.

Usage:
------
    from regenerate_html import regenerate_listing_html
    
    # Regenerate single listing
    regenerate_listing_html('/path/to/listing/folder')
    
    # Regenerate with specific template
    regenerate_listing_html('/path/to/listing/folder', template_name='luna')
"""

import os
import sys
from pathlib import Path
import logging

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from Helper.builder import build_listing_html, get_available_templates
from Helper.database import get_listing_from_mainframe, save_poi_data_to_mainframe
from Helper.poi_fetcher import fetch_pois_for_listing
import asyncio

# Configure logging
logger = logging.getLogger(__name__)


async def refetch_poi_data_for_listing(listing_id, listing_data):
    """
    Re-fetch POI data for a listing from its coordinates.
    
    Args:
        listing_id: Listing ID
        listing_data: Listing data from database
        
    Returns:
        True if POI data was successfully fetched and saved
    """
    try:
        # Get coordinates from listing map data
        map_data = listing_data.get('map_data')
        if not map_data:
            logger.warning(f"No map data found for listing {listing_id} - skipping POI fetch")
            return False
        
        # Extract coordinates
        if isinstance(map_data, str):
            import json
            try:
                map_data = json.loads(map_data)
            except:
                logger.warning(f"Invalid map data format for listing {listing_id}")
                return False
        
        lat = map_data.get('lat')
        lng = map_data.get('lng')
        
        if not (lat and lng):
            logger.warning(f"No coordinates found for listing {listing_id} - skipping POI fetch")
            return False
        
        logger.info(f"🌍 Re-fetching POI data for listing {listing_id} at {lat}, {lng}")
        
        # Fetch fresh POI data
        poi_data, poi_summary = await fetch_pois_for_listing(float(lat), float(lng), radius=500)
        
        if poi_data:
            # Save to database
            success = save_poi_data_to_mainframe(listing_id, poi_data, radius=500)
            if success:
                total_pois = poi_summary.get('total_pois', 0)
                logger.info(f"✅ Updated POI data: {total_pois} POIs across {len(poi_summary.get('categories', {}))} categories")
                return True
            else:
                logger.error(f"Failed to save POI data for listing {listing_id}")
                return False
        else:
            logger.warning(f"No POI data fetched for listing {listing_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error re-fetching POI data for listing {listing_id}: {e}")
        return False


def regenerate_listing_html(folder_path, template_name=None, base_url='', refetch_pois=True):
    """
    Regenerate HTML for a listing using the universal builder system.
    
    This function is called by the dashboard after edits to regenerate
    the static HTML files that will be deployed to web hosting.
    
    Args:
        folder_path: Path to the listing folder (e.g., 'Listings/102312333')
        template_name: Optional template name (uses DB value if not specified)
        base_url: Base URL for absolute paths (optional)
        refetch_pois: Whether to re-fetch POI data from address (default: True)
        
    Returns:
        True if regeneration successful, False otherwise
    """
    try:
        # Extract listing ID from folder path
        folder_path = Path(folder_path)
        listing_id = folder_path.name
        
        # Get listing data from Mainframe.db to determine template
        listing = get_listing_from_mainframe(listing_id)
        if not listing:
            logger.error(f"Listing {listing_id} not found in Mainframe.db")
            return False
        
        # Use template from database if not specified
        if template_name is None:
            template_name = listing.get('template_name', 'luna')
        
        logger.info(f"Regenerating HTML for listing {listing_id} with {template_name} template")
        
        # Re-fetch POI data if requested
        if refetch_pois:
            try:
                poi_success = asyncio.run(refetch_poi_data_for_listing(listing_id, listing))
                if poi_success:
                    logger.info(f"✅ POI data updated for listing {listing_id}")
                else:
                    logger.warning(f"⚠️ POI data update failed for listing {listing_id}")
            except Exception as e:
                logger.error(f"Error during POI re-fetch for listing {listing_id}: {e}")
        
        # Build HTML using universal builder
        html = build_listing_html(
            listing_id=listing_id,
            template_name=template_name,
            base_url=base_url,
            save_to_file=True,
            output_path=folder_path / 'index.html'
        )
        
        if html:
            logger.info(f"✅ Successfully regenerated HTML for listing {listing_id}")
            return True
        else:
            logger.error(f"❌ Failed to regenerate HTML for listing {listing_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error regenerating HTML for {folder_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def regenerate_listing_by_id(listing_id, template_name=None, base_url='', refetch_pois=True):
    """
    Regenerate HTML for a listing by ID.
    
    Args:
        listing_id: Listing ID from Mainframe.db
        template_name: Optional template name (uses DB value if not specified)
        base_url: Base URL for absolute paths (optional)
        refetch_pois: Whether to re-fetch POI data from address (default: True)
        
    Returns:
        True if regeneration successful, False otherwise
    """
    try:
        # Get listing data to find folder path
        listing = get_listing_from_mainframe(listing_id)
        if not listing:
            logger.error(f"Listing {listing_id} not found in Mainframe.db")
            return False
        
        # Get folder path from database
        folder_path = listing.get('folder_path', f'Listings/{listing_id}')
        folder_path = Path(folder_path)
        
        # Ensure folder exists
        if not folder_path.exists():
            logger.warning(f"Creating missing folder: {folder_path}")
            folder_path.mkdir(parents=True, exist_ok=True)
            
            # Create images subfolder
            images_folder = folder_path / 'images'
            images_folder.mkdir(exist_ok=True)
        
        return regenerate_listing_html(folder_path, template_name, base_url, refetch_pois)
        
    except Exception as e:
        logger.error(f"Error regenerating HTML for listing ID {listing_id}: {e}")
        return False


def batch_regenerate_html(template_name=None, status='active', base_url='', refetch_pois=True):
    """
    Regenerate HTML for multiple listings.
    
    Args:
        template_name: Optional template to use for all listings
        status: Listing status filter ('active', 'archived', 'all')
        base_url: Base URL for absolute paths (optional)
        refetch_pois: Whether to re-fetch POI data for each listing (default: True)
        
    Returns:
        Dictionary with counts: {'success': X, 'failed': Y, 'total': Z}
    """
    try:
        from Helper.database import init_mainframe_db
        import sqlite3
        
        # Get all listings from database
        conn = init_mainframe_db()
        c = conn.cursor()
        
        if status == 'all':
            c.execute('SELECT id, template_name FROM listings')
        else:
            c.execute('SELECT id, template_name FROM listings WHERE status = ?', (status,))
        
        listings = c.fetchall()
        conn.close()
        
        results = {
            'success': 0,
            'failed': 0,
            'total': len(listings)
        }
        
        print(f"🔄 Regenerating HTML for {results['total']} listings...")
        print()
        
        for i, (listing_id, db_template) in enumerate(listings, 1):
            template = template_name or db_template or 'luna'
            
            print(f"[{i}/{results['total']}] {listing_id} ({template})...", end=' ')
            
            if regenerate_listing_by_id(listing_id, template, base_url, refetch_pois):
                results['success'] += 1
                print("✅")
            else:
                results['failed'] += 1
                print("❌")
        
        print()
        print("=" * 50)
        print(f"✅ Success: {results['success']}")
        print(f"❌ Failed: {results['failed']}")
        print(f"📊 Total: {results['total']}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in batch regeneration: {e}")
        return {'success': 0, 'failed': 0, 'total': 0}


def get_regeneration_status():
    """
    Get status of HTML regeneration system.
    
    Returns:
        Dictionary with system status information
    """
    try:
        available_templates = get_available_templates()
        
        return {
            'available': True,
            'templates': available_templates,
            'default_template': 'luna',
            'builder_system': 'Universal Builder (Helper/builder.py)',
            'database': 'Mainframe.db'
        }
    except Exception as e:
        return {
            'available': False,
            'error': str(e),
            'templates': [],
            'default_template': None
        }


# CLI interface for testing
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Regenerate listing HTML files')
    parser.add_argument('--listing-id', '-i', help='Regenerate specific listing by ID')
    parser.add_argument('--folder', '-f', help='Regenerate specific listing by folder path')
    parser.add_argument('--template', '-t', help='Template to use (default: from database)')
    parser.add_argument('--batch', '-b', action='store_true', help='Regenerate all listings')
    parser.add_argument('--status', '-s', default='active', 
                       help='Status filter for batch mode (active, archived, all)')
    parser.add_argument('--base-url', '-u', default='', help='Base URL for absolute paths')
    parser.add_argument('--no-poi-refetch', action='store_true', help='Skip POI data re-fetching (use existing data)')
    parser.add_argument('--check', '-c', action='store_true', help='Check system status')
    
    args = parser.parse_args()
    
    # Configure logging for CLI
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    if args.check:
        status = get_regeneration_status()
        print("HTML Regeneration System Status:")
        print("=" * 40)
        print(f"Available: {status['available']}")
        if status['available']:
            print(f"Templates: {', '.join(status['templates'])}")
            print(f"Default: {status['default_template']}")
            print(f"Builder: {status['builder_system']}")
            print(f"Database: {status['database']}")
        else:
            print(f"Error: {status['error']}")
        sys.exit(0)
    
    # Determine POI refetch setting (default True, unless --no-poi-refetch is used)
    refetch_pois = not args.no_poi_refetch
    
    if args.batch:
        results = batch_regenerate_html(
            template_name=args.template,
            status=args.status,
            base_url=args.base_url,
            refetch_pois=refetch_pois
        )
        sys.exit(0 if results['failed'] == 0 else 1)
    
    if args.listing_id:
        success = regenerate_listing_by_id(
            listing_id=args.listing_id,
            template_name=args.template,
            base_url=args.base_url,
            refetch_pois=refetch_pois
        )
        sys.exit(0 if success else 1)
    
    if args.folder:
        success = regenerate_listing_html(
            folder_path=args.folder,
            template_name=args.template,
            base_url=args.base_url,
            refetch_pois=refetch_pois
        )
        sys.exit(0 if success else 1)
    
    # No arguments provided
    parser.print_help()
    sys.exit(1)
