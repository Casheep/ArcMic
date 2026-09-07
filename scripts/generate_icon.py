import math
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


def point_on_circle(radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return CENTRE + radius * math.cos(radians), CENTRE + radius * math.sin(radians)


image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# A single open audio arc keeps ArcMic recognisable without competing with the
# MaoMao artwork. Pillow arc strokes have square ends, so add circular caps.
arc_radius = 106 * SCALE
arc_width = 20 * SCALE
arc_box = (CENTRE - arc_radius, CENTRE - arc_radius, CENTRE + arc_radius, CENTRE + arc_radius)
arc_start, arc_end = 340, 560
draw.arc(arc_box, start=arc_start, end=arc_end, fill=ACCENT, width=arc_width)
cap_radius = arc_width / 2
for angle in (arc_start, arc_end):
    x, y = point_on_circle(arc_radius - arc_width / 2, angle)
    draw.ellipse((x - cap_radius, y - cap_radius, x + cap_radius, y + cap_radius), fill=ACCENT)

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
