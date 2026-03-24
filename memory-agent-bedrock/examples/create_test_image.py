#!/usr/bin/env python3
"""Create a simple test image for demonstration."""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Please install Pillow: pip install Pillow")
    exit(1)

# Create a simple test image
img = Image.new('RGB', (800, 400), color='white')
draw = ImageDraw.Draw(img)

# Draw some text
try:
    # Try to use a better font
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
except:
    # Fallback to default
    font = ImageFont.load_default()

# Draw title
draw.text((50, 50), "Memory Agent Test Image", fill='black', font=font)

# Draw some content
try:
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
except:
    font_small = ImageFont.load_default()

draw.text((50, 150), "This image contains:", fill='black', font=font_small)
draw.text((50, 200), "• Text content", fill='blue', font=font_small)
draw.text((50, 240), "• Visual elements", fill='green', font=font_small)
draw.text((50, 280), "• Structured information", fill='red', font=font_small)

# Draw a simple shape
draw.rectangle([600, 100, 750, 250], outline='purple', width=3)
draw.ellipse([610, 110, 740, 240], outline='orange', width=2)

# Save
output_path = "test_image.png"
img.save(output_path)
print(f"✓ Created test image: {output_path}")
print(f"  You can now upload this via: POST /ingest/file")
