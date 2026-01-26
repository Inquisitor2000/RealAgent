#!/usr/bin/env python
"""
Clean Mainframe.db - Remove test entries for easier testing
"""

import sqlite3
import sys

def cleanup_database(listing_ids=None, confirm=True):
    """
    Clean database entries.
    
    Args:
        listing_ids: List of specific listing IDs to remove, or None to remove all
        confirm: Whether to ask for confirmation before deletion
    """
    conn = sqlite3.connect('Mainframe.db')
    cursor = conn.cursor()
    
    # Get current counts
    cursor.execute("SELECT COUNT(*) FROM listings")
    total_listings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_images")
    total_images = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_features")
    total_features = cursor.fetchone()[0]
    
    # Get feature language breakdown
    cursor.execute("SELECT lang, COUNT(*) FROM listing_features GROUP BY lang")
    features_by_lang = dict(cursor.fetchall())
    
    cursor.execute("SELECT COUNT(*) FROM listing_amenities")
    total_amenities = cursor.fetchone()[0]
    
    # Get amenity language breakdown
    cursor.execute("SELECT lang, COUNT(*) FROM listing_amenities GROUP BY lang")
    amenities_by_lang = dict(cursor.fetchall())
    
    cursor.execute("SELECT COUNT(*) FROM listing_map")
    total_maps = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_pois")
    total_pois = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM journal_entries")
    total_journal = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM geocode_cache")
    total_geocache = cursor.fetchone()[0]
    
    print("=" * 60)
    print("DATABASE CLEANUP TOOL")
    print("=" * 60)
    print(f"\nCurrent database status:")
    print(f"  Listings: {total_listings}")
    print(f"  Images: {total_images}")
    print(f"  Features: {total_features}")
    if features_by_lang:
        for lang, count in sorted(features_by_lang.items()):
            print(f"    └─ {lang}: {count}")
    print(f"  Amenities: {total_amenities}")
    if amenities_by_lang:
        for lang, count in sorted(amenities_by_lang.items()):
            print(f"    └─ {lang}: {count}")
    print(f"  Maps: {total_maps}")
    print(f"  POIs: {total_pois}")
    print(f"  Journal Entries: {total_journal}")
    print(f"  Geocode Cache: {total_geocache}")
    
    if listing_ids:
        print(f"\n⚠️  Will delete specific listings: {', '.join(listing_ids)}")
    else:
        print(f"\n⚠️  Will delete ALL listings!")
    
    if confirm:
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled")
            conn.close()
            return False
    
    print("\n🗑️  Cleaning database...")
    
    if listing_ids:
        # Delete specific listings
        for listing_id in listing_ids:
            print(f"  Deleting listing {listing_id}...")
            cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
            # Related data will be deleted automatically via CASCADE
    else:
        # Delete all listings and related data
        cursor.execute("DELETE FROM listings")
        cursor.execute("DELETE FROM listing_images")
        cursor.execute("DELETE FROM listing_features")
        cursor.execute("DELETE FROM listing_amenities")
        cursor.execute("DELETE FROM listing_map")
        cursor.execute("DELETE FROM listing_pois")
        cursor.execute("DELETE FROM journal_entries")
        cursor.execute("DELETE FROM geocode_cache")
    
    conn.commit()
    
    # Get new counts
    cursor.execute("SELECT COUNT(*) FROM listings")
    new_listings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_images")
    new_images = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_features")
    new_features = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_amenities")
    new_amenities = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_map")
    new_maps = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM listing_pois")
    new_pois = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM journal_entries")
    new_journal = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM geocode_cache")
    new_geocache = cursor.fetchone()[0]
    
    print("\n✅ Cleanup complete!")
    print(f"\nNew database status:")
    print(f"  Listings: {new_listings} (removed {total_listings - new_listings})")
    print(f"  Images: {new_images} (removed {total_images - new_images})")
    print(f"  Features: {new_features} (removed {total_features - new_features})")
    print(f"  Amenities: {new_amenities} (removed {total_amenities - new_amenities})")
    print(f"  Maps: {new_maps} (removed {total_maps - new_maps})")
    print(f"  POIs: {new_pois} (removed {total_pois - new_pois})")
    print(f"  Journal Entries: {new_journal} (removed {total_journal - new_journal})")
    print(f"  Geocode Cache: {new_geocache} (removed {total_geocache - new_geocache})")
    
    conn.close()
    return True


if __name__ == "__main__":
    print("\n🧹 Mainframe.db Cleanup Script - Auto-cleaning ALL listings...")
    cleanup_database(listing_ids=None, confirm=False)
