from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

OUTPUT_SIZE = 256
SCALE = 4
SIZE = OUTPUT_SIZE * SCALE
CENTRE = SIZE / 2
ACCENT = (80, 108, 245, 255)

image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# A complete, even ring stays clean at taskbar and tray sizes and does not
# create competing endpoints around the MaoMao portrait.
arc_radius = 106 * SCALE
arc_width = 20 * SCALE
arc_box = (CENTRE - arc_radius, CENTRE - arc_radius, CENTRE + arc_radius, CENTRE + arc_radius)
draw.ellipse(arc_box, outline=ACCENT, width=arc_width)

# Use the existing MaoMao project artwork as the circular centre mark.
portrait_radius = 74 * SCALE
border_radius = 79 * SCALE
draw.ellipse(
    (CENTRE - border_radius, CENTRE - border_radius, CENTRE + border_radius, CENTRE + border_radius),
    fill=(255, 255, 255, 255),
)
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
