#!/usr/bin/env python3
"""
POI (Points of Interest) Fetcher for RealAgent
Fetches POI data from Overpass API during listing creation to eliminate runtime API calls.
"""

import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Tuple, Optional
import urllib.parse

class POIFetcher:
    """
    Fetches POI data from Overpass API for pre-generation during listing creation.
    
    Performance & Limits:
    - Timeout: 45 seconds for entire POI fetch operation
    - Max POIs per main category: 10 (configurable via max_pois_per_group)
    - Total categories: 5 (schools, medical, restaurants, supermarkets, banks)
    - Maximum total POIs: ~50 POIs (5 categories × 10 POIs each)
    - Early termination: Each category group returns as soon as data is fetched
    - Only waits full 90s if API is slow/unresponsive
    """
    
    def __init__(self, verbose: bool = True):
        self.base_url = "https://overpass-api.de/api/interpreter"
        self.timeout = 45  # 45 seconds timeout
        self.retry_delay = 2
        self.max_retries = 3
        self.max_pois_per_group = 10  # Maximum POIs per main category group
        self.verbose = verbose  # Control debug output
        
        # POI categories with their Overpass queries (extracted from Luna.html)
        self.poi_categories = {
            'kindergartens': {
                'name': 'Kindergartens',
                'icon': '🎒',
                'color': '#1f8efa',
                'parent': 'schools',
                'query': '''
                    [out:json][timeout:20];
                    (
                      nwr["amenity"="kindergarten"](around:{radius},{lat},{lng});
                      nwr["amenity"="childcare"](around:{radius},{lat},{lng});
                      nwr["building"="kindergarten"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 5;
                '''
            },
            'schools-other': {
                'name': 'Schools & Universities',
                'icon': '🏫',
                'color': '#f39c12',
                'parent': 'schools',
                'query': '''
                    [out:json][timeout:20];
                    (
                      nwr["amenity"~"^(school|college|university|language_school)$"](around:{radius},{lat},{lng});
                      nwr["building"~"^(school|university)$"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 5;
                '''
            },
            'hospitals': {
                'name': 'Hospitals & Medical Centers',
                'icon': '🏥',
                'color': '#e53935',
                'parent': 'medical',
                'query': '''
                    [out:json][timeout:20];
                    (
                      nwr["amenity"~"^(hospital|clinic|doctors|dentist)$"](around:{radius},{lat},{lng});
                      nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"](around:{radius},{lat},{lng});
                      nwr["building"="hospital"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 6;
                '''
            },
            'pharmacies': {
                'name': 'Pharmacies & Drugstores',
                'icon': '💊',
                'color': '#2ecc71',
                'parent': 'medical',
                'query': '''
                    [out:json][timeout:15];
                    (
                      nwr["amenity"="pharmacy"](around:{radius},{lat},{lng});
                      nwr["healthcare"="pharmacy"](around:{radius},{lat},{lng});
                      nwr["shop"="chemist"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 4;
                '''
            },
            'supermarkets': {
                'name': 'Supermarkets',
                'icon': '🛒',
                'color': '#27ae60',
                'query': '''
                    [out:json][timeout:15];
                    (
                      nwr["shop"~"^(supermarket|convenience|grocery|general|mall)$"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 10;
                '''
            },
            'bank-branches': {
                'name': 'Bank Branches',
                'icon': '$',
                'color': '#8e44ad',
                'parent': 'banks',
                'query': '''
                    [out:json][timeout:15];
                    (
                      nwr["amenity"="bank"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 4;
                '''
            },
            'atms': {
                'name': 'ATMs & Currency Exchange',
                'icon': '💳',
                'color': '#f1c40f',
                'parent': 'banks',
                'query': '''
                    [out:json][timeout:15];
                    (
                      nwr["amenity"~"^(atm|bureau_de_change)$"](around:{radius},{lat},{lng});
                      nwr["atm"="yes"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 6;
                '''
            },
            'restaurants': {
                'name': 'Restaurants & Cafes',
                'icon': '🍽️',
                'color': '#e67e22',
                'query': '''
                    [out:json][timeout:15];
                    (
                      nwr["amenity"~"^(restaurant|cafe|fast_food|bar|pub)$"](around:{radius},{lat},{lng});
                    );
                    out center meta qt 10;
                '''
            }
        }
        
        # Parent category mappings
        self.parent_to_children = {
            'schools': ['kindergartens', 'schools-other'],
            'medical': ['hospitals', 'pharmacies'],
            'banks': ['bank-branches', 'atms'],
            'supermarkets': ['supermarkets'],
            'restaurants': ['restaurants']
        }

    async def fetch_single_poi_category(self, session: aiohttp.ClientSession, 
                                      lat: float, lng: float, poi_type: str, 
                                      radius: int = 500) -> List[Dict]:
        """Fetch POI data for a single category."""
        
        if poi_type not in self.poi_categories:
            print(f"⚠️ Unknown POI type: {poi_type}")
            return []
        
        poi_config = self.poi_categories[poi_type]
        query = poi_config['query'].format(radius=radius, lat=lat, lng=lng).strip()
        
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    self.base_url,
                    data={'data': query},
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={'User-Agent': 'RealAgent/1.0 POI Fetcher'}
                ) as response:
                    
                    if response.status == 429:
                        wait_time = self.retry_delay * (2 ** attempt)
                        # Show cyclic animation during rate limit wait
                        await self._show_spotlight_animation(wait_time)
                        continue
                    
                    if response.status == 504:
                        # Show cyclic animation during timeout retry
                        await self._show_spotlight_animation(self.retry_delay)
                        continue
                    
                    response.raise_for_status()
                    data = await response.json()
                    
                    raw_results = data.get('elements', [])
                    processed_results = self._process_poi_results(raw_results, poi_type)
                    
                    print(f"✅ Fetched {len(processed_results)} {poi_type} POIs")
                    return processed_results
                    
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    # Show cyclic animation during timeout retry
                    await self._show_spotlight_animation(self.retry_delay)
                    
            except Exception as e:
                print(f"❌ Error fetching {poi_type}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        print(f"❌ Failed to fetch {poi_type} after {self.max_retries} attempts")
        return []

    def _process_poi_results(self, raw_results: List[Dict], poi_type: str) -> List[Dict]:
        """Process raw Overpass API results into standardized POI format."""
        processed = []
        seen_locations = set()
        
        for element in raw_results:
            try:
                # Get coordinates
                if element.get('type') == 'node':
                    lat, lng = element.get('lat'), element.get('lon')
                elif 'center' in element:
                    lat, lng = element['center']['lat'], element['center']['lon']
                else:
                    continue
                
                if not (lat and lng):
                    continue
                
                # Deduplicate by location (within 10m)
                location_key = f"{round(lat, 4)},{round(lng, 4)}"
                if location_key in seen_locations:
                    continue
                seen_locations.add(location_key)
                
                # Extract POI information
                tags = element.get('tags', {})
                name = (tags.get('name') or 
                       tags.get('brand') or 
                       tags.get('operator') or 
                       'Unnamed')
                
                # Clean up name
                if name and len(name) > 50:
                    name = name[:47] + "..."
                
                poi_data = {
                    'id': element.get('id'),
                    'type': element.get('type'),
                    'lat': lat,
                    'lng': lng,
                    'name': name,
                    'category': poi_type,
                    'tags': {
                        'amenity': tags.get('amenity'),
                        'shop': tags.get('shop'),
                        'healthcare': tags.get('healthcare'),
                        'building': tags.get('building'),
                        'operator': tags.get('operator'),
                        'brand': tags.get('brand'),
                        'website': tags.get('website'),
                        'phone': tags.get('phone'),
                        'opening_hours': tags.get('opening_hours'),
                        'addr:street': tags.get('addr:street'),
                        'addr:housenumber': tags.get('addr:housenumber')
                    }
                }
                
                # Remove None values from tags
                poi_data['tags'] = {k: v for k, v in poi_data['tags'].items() if v is not None}
                
                processed.append(poi_data)
                
            except Exception as e:
                print(f"⚠️ Error processing POI element: {e}")
                continue
        
        return processed

    async def fetch_all_pois_for_location(self, lat: float, lng: float, 
                                        radius: int = 500) -> Dict[str, List[Dict]]:
        """Fetch all POI categories for a given location using optimized combined queries."""
        
        # Start single animation for entire POI search process
        animation_task = asyncio.create_task(self._show_continuous_animation())
        
        try:
            async with aiohttp.ClientSession() as session:
                # Use combined query approach with 45-second timeout
                results = await asyncio.wait_for(
                    self._fetch_pois_combined(session, lat, lng, radius),
                    timeout=45.0
                )
            return results
            
        except asyncio.TimeoutError:
            print("\r" + " " * 60 + "\r", end="", flush=True)  # Clear animation line
            print("⏰ POI search timed out after 90 seconds, returning partial results")
            # Return whatever results we have so far
            return getattr(self, '_partial_results', {})
            
        finally:
            # Always cancel animation task
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass
            print("\r" + " " * 60 + "\r", end="", flush=True)  # Clear animation line

    async def _fetch_pois_combined(self, session: aiohttp.ClientSession, 
                                 lat: float, lng: float, radius: int) -> Dict[str, List[Dict]]:
        """Fetch POIs using combined queries for better performance."""
        
        # Initialize partial results tracking
        self._partial_results = {}
        
        # Group POI categories - 5 main categories with subcategories
        # Each main category is limited to self.max_pois_per_group (default: 10 POIs)
        # Total max POIs: 5 groups × 10 POIs = ~50 POIs
        # Restaurants and supermarkets moved earlier in sequence to avoid timeout issues
        query_groups = {
            'schools': ['kindergartens', 'schools-other'],
            'medical': ['hospitals', 'pharmacies'],
            'restaurants': ['restaurants'],  # Prioritized
            'supermarkets': ['supermarkets'],  # Prioritized
            'banks': ['bank-branches', 'atms']
        }
        
        all_results = {}
        
        if self.verbose:
            print(f"\n🔍 Starting POI fetch for {len(query_groups)} category groups...")
        
        for group_name, poi_types in query_groups.items():
            if self.verbose:
                print(f"\n🔎 Fetching {group_name} group ({', '.join(poi_types)})...")
            try:
                # Create combined query for this group
                combined_query = self._build_combined_query(poi_types, lat, lng, radius)
                
                # Execute combined query
                group_results = await self._execute_combined_query(
                    session, combined_query, poi_types, lat, lng, radius
                )
                
                # Merge results
                all_results.update(group_results)
                
                # Update partial results for timeout scenarios
                self._partial_results.update(group_results)
                
                # Log detailed results for each category group (only when verbose)
                if self.verbose:
                    for poi_type in poi_types:
                        poi_count = len(group_results.get(poi_type, []))
                        if poi_count > 0:
                            print(f"   ✅ {group_name.capitalize()}: Fetched {poi_count} {poi_type} POIs")
                        else:
                            print(f"   ⚠️ {group_name.capitalize()}: No {poi_type} found in this area")
                
                # Small delay between groups to be respectful to API
                await asyncio.sleep(0.3)
                
            except Exception as e:
                if self.verbose:
                    print(f"   ❌ ERROR: Failed to fetch {group_name} POIs: {e}")
                    import traceback
                    traceback.print_exc()
                # Initialize empty results for failed group
                for poi_type in poi_types:
                    all_results[poi_type] = []
        
        # Final summary (only when verbose)
        if self.verbose:
            total_fetched = sum(len(pois) for pois in all_results.values())
            print(f"\n✅ POI fetch complete: {total_fetched} total POIs across {len(all_results)} categories")
        
        return all_results

    def _build_combined_query(self, poi_types: List[str], lat: float, lng: float, radius: int) -> str:
        """Build a combined Overpass query for multiple POI types."""
        
        # Start query
        query_parts = ["[out:json][timeout:25];", "("]
        
        # Add queries for each POI type in the group
        for poi_type in poi_types:
            if poi_type in self.poi_categories:
                poi_config = self.poi_categories[poi_type]
                # Extract the main query part (between the parentheses)
                base_query = poi_config['query'].strip()
                
                # Extract query elements from the template
                if 'kindergarten' in base_query or 'childcare' in base_query:
                    query_parts.extend([
                        f'  nwr["amenity"="kindergarten"](around:{radius},{lat},{lng});',
                        f'  nwr["amenity"="childcare"](around:{radius},{lat},{lng});',
                        f'  nwr["building"="kindergarten"](around:{radius},{lat},{lng});'
                    ])
                elif 'school' in base_query:
                    query_parts.extend([
                        f'  nwr["amenity"~"^(school|college|university|language_school)$"](around:{radius},{lat},{lng});',
                        f'  nwr["building"~"^(school|university)$"](around:{radius},{lat},{lng});'
                    ])
                elif 'hospital' in base_query:
                    query_parts.extend([
                        f'  nwr["amenity"~"^(hospital|clinic|doctors|dentist)$"](around:{radius},{lat},{lng});',
                        f'  nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"](around:{radius},{lat},{lng});',
                        f'  nwr["building"="hospital"](around:{radius},{lat},{lng});'
                    ])
                elif 'pharmacy' in base_query:
                    query_parts.extend([
                        f'  nwr["amenity"="pharmacy"](around:{radius},{lat},{lng});',
                        f'  nwr["healthcare"="pharmacy"](around:{radius},{lat},{lng});',
                        f'  nwr["shop"="chemist"](around:{radius},{lat},{lng});'
                    ])
                elif 'supermarket' in base_query:
                    query_parts.append(
                        f'  nwr["shop"~"^(supermarket|convenience|grocery|general|mall)$"](around:{radius},{lat},{lng});'
                    )
                elif 'bank' in base_query:
                    query_parts.append(f'  nwr["amenity"="bank"](around:{radius},{lat},{lng});')
                elif 'atm' in base_query:
                    query_parts.extend([
                        f'  nwr["amenity"~"^(atm|bureau_de_change)$"](around:{radius},{lat},{lng});',
                        f'  nwr["atm"="yes"](around:{radius},{lat},{lng});'
                    ])
                elif 'restaurant' in base_query:
                    query_parts.append(
                        f'  nwr["amenity"~"^(restaurant|cafe|fast_food|bar|pub)$"](around:{radius},{lat},{lng});'
                    )
        
        # Close query
        query_parts.extend([");", "out center meta qt 50;"])
        
        return "\n".join(query_parts)

    async def _execute_combined_query(self, session: aiohttp.ClientSession, query: str, 
                                    poi_types: List[str], lat: float, lng: float, 
                                    radius: int) -> Dict[str, List[Dict]]:
        """Execute a combined query and categorize results."""
        
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    self.base_url,
                    data={'data': query},
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={'User-Agent': 'RealAgent/1.0 POI Fetcher'}
                ) as response:
                    
                    if response.status == 429:
                        wait_time = self.retry_delay * (2 ** attempt)
                        # Show cyclic animation during rate limit wait
                        await self._show_spotlight_animation(wait_time)
                        continue
                    
                    if response.status == 504:
                        # Show cyclic animation during timeout retry
                        await self._show_spotlight_animation(self.retry_delay)
                        continue
                    
                    response.raise_for_status()
                    data = await response.json()
                    
                    # Process and categorize results
                    raw_results = data.get('elements', [])
                    categorized_results = self._categorize_combined_results(raw_results, poi_types)
                    
                    # Process each category with 10 POI limit per MAIN CATEGORY GROUP
                    final_results = {}
                    
                    # Count total POIs for this main category group
                    total_group_pois = []
                    for poi_type in poi_types:
                        category_pois = categorized_results.get(poi_type, [])
                        for poi in category_pois:
                            poi['_category'] = poi_type  # Mark which subcategory this belongs to
                            total_group_pois.append(poi)
                    
                    # Limit to configured max POIs total for this main category group
                    limited_group_pois = total_group_pois[:self.max_pois_per_group]
                    
                    # Redistribute back to subcategories
                    for poi_type in poi_types:
                        subcategory_pois = [poi for poi in limited_group_pois if poi.get('_category') == poi_type]
                        # Remove the temporary category marker
                        for poi in subcategory_pois:
                            poi.pop('_category', None)
                        processed_pois = self._process_poi_results(subcategory_pois, poi_type)
                        final_results[poi_type] = processed_pois
                    
                    return final_results
                    
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    # Show cyclic animation during timeout retry
                    await self._show_spotlight_animation(self.retry_delay)
                    
            except Exception as e:
                print(f"❌ Error in combined query: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # Return empty results if all attempts failed
        return {poi_type: [] for poi_type in poi_types}

    def _categorize_combined_results(self, raw_results: List[Dict], poi_types: List[str]) -> Dict[str, List[Dict]]:
        """Categorize combined query results into POI types."""
        
        categorized = {poi_type: [] for poi_type in poi_types}
        
        for element in raw_results:
            tags = element.get('tags', {})
            
            # Determine POI category based on tags
            amenity = tags.get('amenity', '').lower()
            shop = tags.get('shop', '').lower()
            healthcare = tags.get('healthcare', '').lower()
            building = tags.get('building', '').lower()
            
            # Categorization logic
            if amenity in ['kindergarten'] or building == 'kindergarten' or amenity == 'childcare':
                if 'kindergartens' in poi_types:
                    categorized['kindergartens'].append(element)
            elif amenity in ['school', 'college', 'university', 'language_school'] or building in ['school', 'university']:
                if 'schools-other' in poi_types:
                    categorized['schools-other'].append(element)
            elif amenity in ['hospital', 'clinic', 'doctors', 'dentist'] or healthcare in ['hospital', 'clinic', 'doctor', 'centre'] or building == 'hospital':
                if 'hospitals' in poi_types:
                    categorized['hospitals'].append(element)
            elif amenity == 'pharmacy' or healthcare == 'pharmacy' or shop == 'chemist':
                if 'pharmacies' in poi_types:
                    categorized['pharmacies'].append(element)
            elif shop in ['supermarket', 'convenience', 'grocery', 'general', 'mall']:
                if 'supermarkets' in poi_types:
                    categorized['supermarkets'].append(element)
            elif amenity == 'bank':
                if 'bank-branches' in poi_types:
                    categorized['bank-branches'].append(element)
            elif amenity in ['atm', 'bureau_de_change'] or tags.get('atm') == 'yes':
                if 'atms' in poi_types:
                    categorized['atms'].append(element)
            elif amenity in ['restaurant', 'cafe', 'fast_food', 'bar', 'pub']:
                if 'restaurants' in poi_types:
                    categorized['restaurants'].append(element)
        
        return categorized

    async def _show_spotlight_animation(self, duration: float):
        """Show cyclic animation during wait periods, similar to address search animation."""
        if not self.verbose:
            await asyncio.sleep(duration)
            return
            
        progress_chars = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']  # Spinner characters
        progress_idx = 0
        
        # Calculate animation cycles (0.5s per frame)
        total_frames = int(duration / 0.5)
        
        for frame in range(total_frames):
            print(f"\rℹ️ Spotlight for local organizations {progress_chars[progress_idx % len(progress_chars)]}", end="", flush=True)
            progress_idx += 1
            await asyncio.sleep(0.5)
        
        # Clear the animation line
        print("\r" + " " * 60 + "\r", end="", flush=True)

    async def _show_continuous_animation(self):
        """Show continuous animation during API requests."""
        if not self.verbose:
            return
            
        progress_chars = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']  # Spinner characters
        progress_idx = 0
        
        while True:
            print(f"\rℹ️ Spotlight for local organizations {progress_chars[progress_idx % len(progress_chars)]}", end="", flush=True)
            progress_idx += 1
            await asyncio.sleep(0.5)

    def create_poi_summary(self, poi_data: Dict[str, List[Dict]]) -> Dict:
        """Create a summary of POI data for quick reference."""
        summary = {
            'total_pois': sum(len(pois) for pois in poi_data.values()),
            'categories': {},
            'generated_at': int(time.time()),
            'radius': 500  # Default radius used
        }
        
        for category, pois in poi_data.items():
            summary['categories'][category] = {
                'count': len(pois),
                'names': [poi['name'] for poi in pois[:5]]  # First 5 names as sample
            }
        
        return summary

# Async helper function for easy integration
async def fetch_pois_for_listing(lat: float, lng: float, radius: int = 500, verbose: bool = True) -> Tuple[Dict[str, List[Dict]], Dict]:
    """
    Convenience function to fetch POI data for a listing location.
    
    Args:
        lat: Latitude
        lng: Longitude
        radius: Search radius in meters
        verbose: Whether to print progress messages
    
    Returns:
        Tuple of (poi_data, poi_summary)
    """
    fetcher = POIFetcher(verbose=verbose)
    poi_data = await fetcher.fetch_all_pois_for_location(lat, lng, radius)
    poi_summary = fetcher.create_poi_summary(poi_data)
    
    return poi_data, poi_summary

if __name__ == "__main__":
    # Test the POI fetcher
    async def test_poi_fetcher():
        # Test with Chișinău coordinates
        lat, lng = 47.0533205, 28.8463046
        poi_data, summary = await fetch_pois_for_listing(lat, lng)
        
        print("\n" + "="*60)
        print("POI FETCH SUMMARY")
        print("="*60)
        print(f"Total POIs: {summary['total_pois']}")
        print(f"Categories: {len(summary['categories'])}")
        
        for category, info in summary['categories'].items():
            print(f"  {category}: {info['count']} POIs")
            if info['names']:
                print(f"    Sample: {', '.join(info['names'])}")
        
        # Save test data
        with open('test_poi_data.json', 'w', encoding='utf-8') as f:
            json.dump({
                'poi_data': poi_data,
                'summary': summary
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\nTest data saved to test_poi_data.json")
    
    asyncio.run(test_poi_fetcher())
