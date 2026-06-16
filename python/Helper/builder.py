"""
Universal Template Builder Router
==================================

This module routes HTML generation to the appropriate template builder.
It provides a unified interface for building listings with any template.

Usage:
------
    from Helper.builder import build_listing_html
    
    # Build with Luna template (default)
    html = build_listing_html('12345')
    
    # Build with specific template
    html = build_listing_html('12345', template_name='nova')
    
    # Build and save to file
    html = build_listing_html('12345', save_to_file=True)

Adding New Templates:
--------------------
1. Create Templates/[TemplateName]/builder.py
2. Implement build_[templatename]_html() function
3. Add to TEMPLATE_REGISTRY below
4. That's it! The router will handle the rest.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Callable

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Templates.Luna.builder import build_luna_html
from Templates.Thunder.builder import build_thunder_html
# from Templates.Nova.builder import build_nova_html  # Future template
# from Templates.Apex.builder import build_apex_html  # Future template


# Template Registry
# -----------------
# Maps template names to their builder functions and paths
TEMPLATE_REGISTRY: Dict[str, Dict] = {
    'luna': {
        'builder': build_luna_html,
        'template_path': project_root / 'Templates' / 'Luna' / 'Luna.html',
        'css_path': project_root / 'Templates' / 'Luna' / 'Luna.css',
        'descriptions': {
            'en': 'Modern card-based template with dark mode support',
            'ro': 'Template modern bazat pe carduri cu suport pentru mod întunecat',
            'ru': 'Современный шаблон на основе карточек с поддержкой темного режима'
        }
    },
    'thunder': {
        'builder': build_thunder_html,
        'template_path': project_root / 'Templates' / 'Thunder' / 'Thunder.html',
        'css_path': project_root / 'Templates' / 'Thunder' / 'Thunder.css',
        'descriptions': {
            'en': 'Tinder-style swipeable template with minimalist white/black design',
            'ro': 'Template stil Tinder cu design minimalist alb/negru',
            'ru': 'Шаблон в стиле Tinder с минималистичным бело-черным дизайном'
        }
    },
    # Future templates will be added here
    # 'nova': {
    #     'builder': build_nova_html,
    #     'template_path': project_root / 'Templates' / 'Nova' / 'Nova.html',
    #     'css_path': project_root / 'Templates' / 'Nova' / 'Nova.css',
    #     'descriptions': {
    #         'en': 'Minimalist template with clean design',
    #         'ro': 'Template minimalist cu design curat',
    #         'ru': 'Минималистичный шаблон с чистым дизайном'
    #     }
    # },
}

# Default template to use when none specified
DEFAULT_TEMPLATE = 'luna'


def get_available_templates() -> list[str]:
    """
    Get list of all available template names.
    
    Returns:
        List of template names (e.g., ['luna', 'nova'])
    """
    return list(TEMPLATE_REGISTRY.keys())


def get_template_info(template_name: str) -> Optional[Dict]:
    """
    Get information about a specific template.
    
    Args:
        template_name: Name of the template (e.g., 'luna')
        
    Returns:
        Dictionary with template info, or None if not found
    """
    return TEMPLATE_REGISTRY.get(template_name)


def validate_template(template_name: str) -> bool:
    """
    Check if a template exists and is valid.
    
    Args:
        template_name: Name of the template to validate
        
    Returns:
        True if template exists and is valid
    """
    if template_name not in TEMPLATE_REGISTRY:
        return False
    
    template_info = TEMPLATE_REGISTRY[template_name]
    
    # Check if template file exists
    if not template_info['template_path'].exists():
        print(f"⚠️  Template file not found: {template_info['template_path']}")
        return False
    
    # Check if builder function exists
    if not callable(template_info['builder']):
        print(f"⚠️  Builder function not callable for template: {template_name}")
        return False
    
    return True


def build_listing_html(
    listing_id: str,
    template_name: str = DEFAULT_TEMPLATE,
    base_url: str = '',
    save_to_file: bool = False,
    output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Universal HTML builder - routes to appropriate template builder.
    
    This is the main entry point for building listing HTML.
    It handles template routing, validation, and optional file saving.
    
    Args:
        listing_id: Listing ID from Mainframe.db
        template_name: Template to use (default: 'luna')
        base_url: Base URL for absolute paths (e.g., 'https://example.com')
        save_to_file: Whether to save HTML to file
        output_path: Custom output path (default: Listings/{listing_id}/index.html)
        
    Returns:
        Generated HTML string, or None if generation failed
        
    Examples:
        >>> # Build with default Luna template
        >>> html = build_listing_html('12345')
        
        >>> # Build with specific template
        >>> html = build_listing_html('12345', template_name='nova')
        
        >>> # Build and save to file
        >>> html = build_listing_html('12345', save_to_file=True)
        
        >>> # Build with custom output path
        >>> html = build_listing_html('12345', save_to_file=True, 
        ...                          output_path=Path('custom/path.html'))
    """
    # Validate template
    if not validate_template(template_name):
        print(f"❌ Invalid template: {template_name}")
        print(f"📋 Available templates: {', '.join(get_available_templates())}")
        return None
    
    # Get template configuration
    template_config = TEMPLATE_REGISTRY[template_name]
    builder_func = template_config['builder']
    template_path = template_config['template_path']
    
    # print(f"🎨 Building listing {listing_id} with {template_name} template...")
    
    # Call template-specific builder
    try:
        html = builder_func(
            listing_id=listing_id,
            template_path=str(template_path),
            base_url=base_url
        )
        
        if html is None:
            print(f"❌ Failed to build HTML for listing {listing_id}")
            return None
        
        # print(f"✅ Successfully built HTML with {template_name} template")
        
        # Save to file if requested
        if save_to_file:
            if output_path is None:
                # Default: Listings/{listing_id}/index.html
                output_path = project_root / 'Listings' / listing_id / 'index.html'
            
            # Create directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write HTML file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # print(f"💾 Saved HTML to: {output_path}")
            
            # Copy CSS file to listing folder
            css_source = template_config['css_path']
            css_dest = output_path.parent / css_source.name
            
            if css_source.exists():
                import shutil
                shutil.copy2(css_source, css_dest)
                # print(f"💾 Copied CSS to: {css_dest}")
        
        return html
        
    except Exception as e:
        print(f"❌ Error building HTML: {e}")
        import traceback
        traceback.print_exc()
        return None


def rebuild_listing(listing_id: str, template_name: Optional[str] = None) -> bool:
    """
    Rebuild HTML for an existing listing.
    
    If template_name is not specified, uses the template stored in the database.
    
    Args:
        listing_id: Listing ID to rebuild
        template_name: Optional template name (uses DB value if not specified)
        
    Returns:
        True if rebuild successful
    """
    from Helper.database import get_listing_from_mainframe
    
    # Get listing data to check template
    listing = get_listing_from_mainframe(listing_id)
    if not listing:
        print(f"❌ Listing {listing_id} not found in database")
        return False
    
    # Use template from database if not specified
    if template_name is None:
        template_name = listing.get('template_name', DEFAULT_TEMPLATE)
    
    print(f"🔄 Rebuilding listing {listing_id} with {template_name} template...")
    
    # Build and save
    html = build_listing_html(
        listing_id=listing_id,
        template_name=template_name,
        save_to_file=True
    )
    
    return html is not None


def batch_rebuild(template_name: Optional[str] = None, status: str = 'active') -> Dict[str, int]:
    """
    Rebuild HTML for multiple listings.
    
    Args:
        template_name: Optional template to use (uses DB value if not specified)
        status: Listing status filter ('active', 'archived', 'all')
        
    Returns:
        Dictionary with counts: {'success': X, 'failed': Y, 'total': Z}
    """
    from Helper.database import get_all_listings
    
    listings = get_all_listings(status=status)
    
    results = {
        'success': 0,
        'failed': 0,
        'total': len(listings)
    }
    
    print(f"🔄 Rebuilding {results['total']} listings...")
    print()
    
    for i, listing in enumerate(listings, 1):
        listing_id = listing['id']
        template = template_name or listing.get('template_name', DEFAULT_TEMPLATE)
        
        print(f"[{i}/{results['total']}] {listing_id}...", end=' ')
        
        if rebuild_listing(listing_id, template):
            results['success'] += 1
        else:
            results['failed'] += 1
        
        print()
    
    print("=" * 50)
    print(f"✅ Success: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📊 Total: {results['total']}")
    
    return results


# CLI interface for testing
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Build listing HTML with templates')
    parser.add_argument('listing_id', help='Listing ID to build')
    parser.add_argument('--template', '-t', default=DEFAULT_TEMPLATE,
                       help=f'Template to use (default: {DEFAULT_TEMPLATE})')
    parser.add_argument('--save', '-s', action='store_true',
                       help='Save HTML to file')
    parser.add_argument('--base-url', '-u', default='',
                       help='Base URL for absolute paths')
    parser.add_argument('--list-templates', '-l', action='store_true',
                       help='List available templates')
    
    args = parser.parse_args()
    
    if args.list_templates:
        print("Available templates:")
        for name, info in TEMPLATE_REGISTRY.items():
            print(f"  • {name}: {info['description']}")
        sys.exit(0)
    
    # Build listing
    html = build_listing_html(
        listing_id=args.listing_id,
        template_name=args.template,
        base_url=args.base_url,
        save_to_file=args.save
    )
    
    if html:
        if not args.save:
            print("\n" + "=" * 50)
            print("Generated HTML (first 500 chars):")
            print("=" * 50)
            print(html[:500] + "...")
        sys.exit(0)
    else:
        sys.exit(1)
