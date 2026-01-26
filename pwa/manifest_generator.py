#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWA Manifest Generator for RealAgent Listings
Generates customized web app manifests for each property listing
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

class PWAManifestGenerator:
    """Generates PWA manifests for real estate listings"""
    
    def __init__(self, base_url: str = "", icon_sizes: List[int] = None):
        self.base_url = base_url.rstrip('/')
        self.icon_sizes = icon_sizes or [48, 72, 96, 128, 144, 152, 167, 180, 192, 384, 512]
        
    def generate_manifest(self, listing_data: Dict[str, Any], listing_folder: str) -> Dict[str, Any]:
        """
        Generate a PWA manifest for a specific listing
        
        Args:
            listing_data: Dictionary containing listing information
            listing_folder: Path to the listing folder
            
        Returns:
            Dictionary containing the PWA manifest
        """
        # Extract listing information
        title = listing_data.get('title', 'Property Listing')
        description = listing_data.get('description', 'Real estate property listing')
        price = listing_data.get('price', '')
        location = listing_data.get('location', '')
        listing_id = listing_data.get('id', '')
        
        # Create app name
        app_name = f"{title}"
        short_name = f"Property {listing_id}" if listing_id else "Property"
        
        # Create description
        app_description = f"{description}"
        if price:
            app_description += f" - {price}"
        if location:
            app_description += f" in {location}"
            
        # Generate start URL
        start_url = f"/{os.path.basename(listing_folder)}/"
        
        # Generate icons from property images
        icons = self._generate_icons(listing_data, listing_folder)
        
        # Determine theme colors based on property type or images
        theme_color, background_color = self._determine_colors(listing_data)
        
        # Create manifest
        manifest = {
            "name": app_name,
            "short_name": short_name[:12],  # Keep short name under 12 chars
            "description": app_description,
            "start_url": start_url,
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": theme_color,
            "background_color": background_color,
            "icons": icons,
            "categories": ["business", "lifestyle", "utilities"],
            "lang": listing_data.get('lang', 'ro'),
            "dir": "ltr",
            "scope": start_url,
            "id": f"realagent-{listing_id}" if listing_id else f"realagent-{hash(start_url)}",
            
            # PWA features
            "prefer_related_applications": False,
            "display_override": ["window-controls-overlay", "standalone", "minimal-ui"],
            
            # Custom properties for RealAgent
            "realagent": {
                "listing_id": listing_id,
                "property_type": listing_data.get('type', 'apartment'),
                "price": price,
                "location": location,
                "generated_at": listing_data.get('timestamp', ''),
                "version": "1.0.0"
            },
            
            # Shortcuts for quick actions
            "shortcuts": self._generate_shortcuts(listing_data, start_url),
            
            # Screenshots for app stores
            "screenshots": self._generate_screenshots(listing_data, listing_folder)
        }
        
        return manifest
    
    def _generate_icons(self, listing_data: Dict[str, Any], listing_folder: str) -> List[Dict[str, Any]]:
        """Generate icon entries for the manifest"""
        icons = []
        
        # Try to use the first property image as app icon
        images = listing_data.get('images', [])
        if images:
            first_image = images[0]
            image_path = f"images/{os.path.basename(first_image)}"
            
            # Generate different sizes
            for size in self.icon_sizes:
                icons.append({
                    "src": image_path,
                    "sizes": f"{size}x{size}",
                    "type": "image/webp",
                    "purpose": "any"
                })
                
                # Add maskable version for adaptive icons
                if size >= 192:
                    icons.append({
                        "src": image_path,
                        "sizes": f"{size}x{size}",
                        "type": "image/webp",
                        "purpose": "maskable"
                    })
        
        # Fallback to default icons
        if not icons:
            for size in self.icon_sizes:
                icons.append({
                    "src": f"/pwa/assets/icon-{size}.png",
                    "sizes": f"{size}x{size}",
                    "type": "image/png",
                    "purpose": "any"
                })
        
        return icons
    
    def _determine_colors(self, listing_data: Dict[str, Any]) -> tuple[str, str]:
        """Determine theme and background colors based on property data"""
        
        # Color schemes based on property type
        color_schemes = {
            'apartment': ('#3b82f6', '#f8fafc'),  # Blue
            'house': ('#059669', '#f0fdf4'),      # Green
            'commercial': ('#7c3aed', '#faf5ff'), # Purple
            'land': ('#ea580c', '#fff7ed'),       # Orange
            'office': ('#0891b2', '#f0f9ff'),     # Cyan
        }
        
        property_type = listing_data.get('type', 'apartment').lower()
        return color_schemes.get(property_type, color_schemes['apartment'])
    
    def _generate_shortcuts(self, listing_data: Dict[str, Any], start_url: str) -> List[Dict[str, Any]]:
        """Generate app shortcuts for quick actions"""
        shortcuts = []
        
        # View images shortcut
        if listing_data.get('images'):
            shortcuts.append({
                "name": "View Photos",
                "short_name": "Photos",
                "description": "View property photos",
                "url": f"{start_url}#gallery",
                "icons": [{
                    "src": "/pwa/assets/icon-192.png",
                    "sizes": "192x192"
                }]
            })
        
        # View map shortcut
        if listing_data.get('coordinates'):
            shortcuts.append({
                "name": "View Map",
                "short_name": "Map",
                "description": "View property location",
                "url": f"{start_url}#map",
                "icons": [{
                    "src": "/pwa/assets/icon-192.png",
                    "sizes": "192x192"
                }]
            })
        
        # Contact shortcut
        if listing_data.get('phone'):
            shortcuts.append({
                "name": "Contact Agent",
                "short_name": "Contact",
                "description": "Contact property agent",
                "url": f"{start_url}#contact",
                "icons": [{
                    "src": "/pwa/assets/icon-192.png",
                    "sizes": "192x192"
                }]
            })
        
        return shortcuts[:4]  # Limit to 4 shortcuts
    
    def _generate_screenshots(self, listing_data: Dict[str, Any], listing_folder: str) -> List[Dict[str, Any]]:
        """Generate screenshot entries for app store listings"""
        screenshots = []
        
        images = listing_data.get('images', [])
        
        # Use first few images as screenshots
        for i, image in enumerate(images[:5]):  # Limit to 5 screenshots
            image_path = f"images/{os.path.basename(image)}"
            screenshots.append({
                "src": image_path,
                "sizes": "1200x800",  # Approximate size
                "type": "image/webp",
                "form_factor": "wide",
                "label": f"Property view {i + 1}"
            })
        
        return screenshots
    
    def save_manifest(self, manifest: Dict[str, Any], output_path: str) -> None:
        """Save manifest to file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    def generate_and_save(self, listing_data: Dict[str, Any], listing_folder: str) -> str:
        """Generate manifest and save to listing folder"""
        manifest = self.generate_manifest(listing_data, listing_folder)
        manifest_path = os.path.join(listing_folder, 'manifest.json')
        self.save_manifest(manifest, manifest_path)
        return manifest_path

# Utility functions for integration with Agent.py
def create_pwa_manifest(listing_data: Dict[str, Any], listing_folder: str, base_url: str = "") -> str:
    """
    Convenience function to create PWA manifest for a listing
    
    Args:
        listing_data: Dictionary containing listing information
        listing_folder: Path to the listing folder
        base_url: Base URL for the application
        
    Returns:
        Path to the generated manifest file
    """
    generator = PWAManifestGenerator(base_url=base_url)
    return generator.generate_and_save(listing_data, listing_folder)

def update_html_for_pwa(html_content: str, manifest_path: str = "manifest.json") -> str:
    """
    Update HTML content to include PWA meta tags and scripts
    
    Args:
        html_content: Original HTML content
        manifest_path: Path to the manifest file (relative to HTML)
        
    Returns:
        Updated HTML content with PWA features
    """
    # PWA meta tags and scripts to inject
    pwa_tags = f'''
  <!-- PWA Manifest -->
  <link rel="manifest" href="{manifest_path}">
  
  <!-- PWA Meta Tags -->
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="RealAgent">
  <meta name="msapplication-TileColor" content="#3b82f6">
  <meta name="msapplication-tap-highlight" content="no">
  
  <!-- Apple Touch Icons -->
  <link rel="apple-touch-icon" href="/pwa/assets/icon-192.png">
  <link rel="apple-touch-icon" sizes="152x152" href="/pwa/assets/icon-152.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/pwa/assets/icon-180.png">
  
  <!-- PWA Initialization Script -->
  <script src="/pwa/pwa-init.js" defer></script>'''
    
    # Insert PWA tags before closing </head> tag
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', pwa_tags + '\n</head>')
    else:
        # Fallback: add after <head> tag
        html_content = html_content.replace('<head>', '<head>' + pwa_tags)
    
    return html_content

# Example usage
if __name__ == "__main__":
    # Example listing data
    sample_listing = {
        'id': '12345',
        'title': 'Apartament 2 camere în Centru',
        'description': 'Apartament modern cu 2 camere în centrul Chișinăului',
        'price': '€85,000',
        'location': 'Centru, Chișinău',
        'type': 'apartment',
        'images': ['image1.webp', 'image2.webp'],
        'coordinates': [47.0105, 28.8638],
        'phone': '+373 69 123 456',
        'timestamp': '2024-01-15',
        'lang': 'ro'
    }
    
    # Generate manifest
    generator = PWAManifestGenerator()
    manifest = generator.generate_manifest(sample_listing, '/path/to/listing')
    
    # Print generated manifest
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
