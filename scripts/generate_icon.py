from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

size = 256
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# Soft, code-native rounded tile and two concentric audio arcs.
draw.rounded_rectangle((10, 10, 246, 246), radius=66, fill=(91, 115, 242, 255))
draw.arc((46, 46, 210, 210), start=38, end=322, fill=(255, 255, 255, 255), width=24)
draw.arc((81, 81, 175, 175), start=38, end=322, fill=(190, 201, 255, 255), width=18)
draw.ellipse((113, 113, 143, 143), fill=(255, 255, 255, 255))

image.save(ASSETS / "app.png")
image.save(ASSETS / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

