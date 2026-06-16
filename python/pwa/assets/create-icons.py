#!/usr/bin/env python3
"""
PWA Icon Generator for RealAgent
Creates placeholder icons in various sizes for PWA functionality
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_pwa_icons():
    """Create PWA icons in various sizes"""
    
    # Icon sizes needed for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Colors
    bg_color = '#3b82f6'  # Blue
    text_color = '#ffffff'  # White
    
    # Create pwa/assets directory
    os.makedirs('pwa/assets', exist_ok=True)
    
    for size in sizes:
        # Create new image
        img = Image.new('RGB', (size, size), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fallback to default
        try:
            # Adjust font size based on icon size
            font_size = max(size // 8, 12)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Draw house icon (simple representation)
        margin = size // 8
        house_size = size - (margin * 2)
        
        # House base (rectangle)
        base_top = size // 2
        base_bottom = size - margin
        base_left = margin
        base_right = size - margin
        
        draw.rectangle([base_left, base_top, base_right, base_bottom], 
                      fill=text_color, outline=text_color)
        
        # House roof (triangle)
        roof_points = [
            (size // 2, margin),  # Top point
            (margin, base_top),   # Left point
            (size - margin, base_top)  # Right point
        ]
        draw.polygon(roof_points, fill=text_color, outline=text_color)
        
        # Door
        door_width = house_size // 4
        door_height = house_size // 3
        door_left = size // 2 - door_width // 2
        door_right = door_left + door_width
        door_top = base_bottom - door_height
        door_bottom = base_bottom
        
        draw.rectangle([door_left, door_top, door_right, door_bottom], 
                      fill=bg_color, outline=bg_color)
        
        # Window
        window_size = house_size // 6
        window_left = base_left + margin
        window_right = window_left + window_size
        window_top = base_top + margin
        window_bottom = window_top + window_size
        
        draw.rectangle([window_left, window_top, window_right, window_bottom], 
                      fill=bg_color, outline=bg_color)
        
        # Save icon
        img.save(f'pwa/assets/icon-{size}.png', 'PNG')
        print(f'Created icon-{size}.png')
    
    # Create badge icon (smaller, for notifications)
    badge_img = Image.new('RGB', (72, 72), bg_color)
    badge_draw = ImageDraw.Draw(badge_img)
    
    # Simple "R" for RealAgent
    try:
        badge_font = ImageFont.truetype("arial.ttf", 48)
    except:
        badge_font = ImageFont.load_default()
    
    # Get text size and center it
    bbox = badge_draw.textbbox((0, 0), "R", font=badge_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (72 - text_width) // 2
    y = (72 - text_height) // 2
    
    badge_draw.text((x, y), "R", fill=text_color, font=badge_font)
    badge_img.save('pwa/assets/badge-72.png', 'PNG')
    print('Created badge-72.png')
    
    print(f'\nCreated {len(sizes) + 1} PWA icons successfully!')
    print('Icons are saved in the pwa/assets/ directory')

if __name__ == "__main__":
    create_pwa_icons()
