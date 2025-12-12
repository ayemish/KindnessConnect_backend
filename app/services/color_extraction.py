# app/services/color_extraction.py

from PIL import Image
import requests
import io
from typing import List, Tuple

# Colormind API URL
COLORMIND_API_URL = 'http://colormind.io/api/'

def get_dominant_rgb_from_image(image_bytes: bytes, num_colors=5) -> List[Tuple[int, int, int]]:
    """
    Analyzes an image to find dominant colors using K-Means clustering (via Pillow's quantize).
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_bytes))
        
        # Resize image for faster processing
        img = img.resize((100, 100))
        
        # Quantize reduces the number of colors, effectively finding dominant ones
        img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=num_colors)
        
        # Get the color palette
        palette = img.getpalette()
        
        # Extract the RGB tuples for the dominant colors
        dominant_rgbs = []
        for i in range(num_colors):
            r = palette[i * 3]
            g = palette[i * 3 + 1]
            b = palette[i * 3 + 2]
            dominant_rgbs.append((r, g, b))
            
        return dominant_rgbs
        
    except Exception as e:
        print(f"Error extracting dominant colors: {e}")
        return []

def get_palette_from_colors(dominant_rgbs: List[Tuple[int, int, int]]) -> Tuple[str, str]:
   
    
    input_colors = [list(rgb) for rgb in dominant_rgbs[:2]]
    while len(input_colors) < 5:
        input_colors.append("N")

    try:
        response = requests.post(
            COLORMIND_API_URL,
            json={"input": input_colors, "model": "default"}
        )
        response.raise_for_status() 
        
        data = response.json()
        palette_rgb = data.get('result', [])
        
        if len(palette_rgb) < 5:
             
             return "#1D4ED8", "#EFF6FF" 
        
       
        primary_rgb = palette_rgb[3]
        light_bg_rgb = palette_rgb[0]
        
      
        def rgb_to_hex(rgb):
            return '#%02x%02x%02x' % tuple(rgb)

        primary_hex = rgb_to_hex(primary_rgb)
        light_bg_hex = rgb_to_hex(light_bg_rgb)
        
        return primary_hex, light_bg_hex

    except requests.exceptions.RequestException as e:
        print(f"Colormind API Request failed: {e}")
        # Default safety fallback colors if the API call fails
        return "#1D4ED8", "#EFF6FF"