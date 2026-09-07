from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

OUTPUT_SIZE = 256
SCALE = 4
SIZE = OUTPUT_SIZE * SCALE
CENTRE = SIZE / 2

image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

# Use the MaoMao artwork directly as the icon, without a competing outer ring.
portrait_radius = 110 * SCALE
portrait_size = round(portrait_radius * 2)
with Image.open(ASSETS / "maomao-headphones.png") as source:
    portrait = ImageOps.fit(source.convert("RGBA"), (portrait_size, portrait_size), method=Image.Resampling.LANCZOS)
mask = Image.new("L", (portrait_size, portrait_size), 0)
ImageDraw.Draw(mask).ellipse((0, 0, portrait_size - 1, portrait_size - 1), fill=255)
image.paste(
    portrait,
    (round(CENTRE - portrait_radius), round(CENTRE - portrait_radius)),
    mask,
)

image = image.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)
image.save(ASSETS / "app.png", optimize=True)
image.save(
    ASSETS / "app.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
