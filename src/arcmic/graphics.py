from __future__ import annotations

import math

from PIL import Image, ImageDraw


SUPERSAMPLE = 4


def _size(width: int, height: int) -> tuple[int, int]:
    return max(1, int(width)), max(1, int(height))


def _finish(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.resize(_size(width, height), Image.Resampling.LANCZOS)


def meter_level_from_amplitude(amplitude: float, floor_db: float = -60.0) -> float:
    """Map a linear audio peak to a useful logarithmic display position."""
    amplitude = min(1.0, max(0.0, float(amplitude)))
    if amplitude <= 0.0:
        return 0.0
    decibels = 20.0 * math.log10(amplitude)
    return min(1.0, max(0.0, (decibels - floor_db) / -floor_db))


def _centred_arc(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    start: float,
    end: float,
    fill: str,
    width: int,
) -> None:
    """Draw an antialiased arc whose stroke is centred on ``box``.

    Pillow draws wide arcs inside their bounding box, while Tk draws the
    outline around the ellipse centreline. Expanding by half the stroke keeps
    the visible arc aligned with the dial's pointer geometry.
    """
    width = max(1, int(width))
    half_width = width / 2
    left, top, right, bottom = box
    draw.arc(
        (left - half_width, top - half_width, right + half_width, bottom + half_width),
        start=start,
        end=end,
        fill=fill,
        width=width,
    )
    centre_x = (left + right) / 2
    centre_y = (top + bottom) / 2
    radius_x = (right - left) / 2
    radius_y = (bottom - top) / 2
    for angle in (start, end):
        radians = math.radians(angle)
        x = centre_x + radius_x * math.cos(radians)
        y = centre_y + radius_y * math.sin(radians)
        draw.ellipse(
            (x - half_width, y - half_width, x + half_width, y + half_width),
            fill=fill,
        )


def _capsule(
    draw: ImageDraw.ImageDraw,
    left: float,
    top: float,
    right: float,
    bottom: float,
    fill: str,
) -> None:
    """Draw a pill with exact semicircular ends instead of corner rounding."""
    radius = (bottom - top) / 2
    right = max(right, left + radius * 2)
    draw.rectangle((left + radius, top, right - radius, bottom), fill=fill)
    draw.ellipse((left, top, left + radius * 2, bottom), fill=fill)
    draw.ellipse((right - radius * 2, top, right, bottom), fill=fill)


def rounded_panel(
    width: int,
    height: int,
    radius: float,
    *,
    fill: str,
    background: str,
    outline: str | None = None,
    outline_width: float = 1,
) -> Image.Image:
    width, height = _size(width, height)
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (width * factor, height * factor), background)
    draw = ImageDraw.Draw(image)
    inset = max(factor / 2, outline_width * factor / 2)
    draw.rounded_rectangle(
        (inset, inset, width * factor - inset - 1, height * factor - inset - 1),
        radius=max(0, radius * factor),
        fill=fill,
        outline=outline,
        width=max(1, round(outline_width * factor)) if outline else 1,
    )
    return _finish(image, width, height)


def pill_switch(width: int, height: int, scale: float, value: bool, *, background: str, accent: str) -> Image.Image:
    width, height = _size(width, height)
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (width * factor, height * factor), background)
    draw = ImageDraw.Draw(image)
    track = accent if value else "#CED2DA"
    margin = max(1, round(scale)) * factor
    draw.rounded_rectangle(
        (margin, margin, width * factor - margin - 1, height * factor - margin - 1),
        radius=height * factor / 2,
        fill=track,
    )
    radius = 11 * scale * factor
    centre_x = (width - height / 2 if value else height / 2) * factor
    centre_y = height * factor / 2
    draw.ellipse(
        (centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius),
        fill="white",
    )
    return _finish(image, width, height)


def gain_dial(
    width: int,
    height: int,
    scale: float,
    value: float,
    maximum: float,
    *,
    background: str,
    track: str,
    colour: str,
    start: float,
    span: float,
    centre: tuple[float, float],
    radius: float,
) -> Image.Image:
    width, height = _size(width, height)
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (width * factor, height * factor), background)
    draw = ImageDraw.Draw(image)
    cx, cy = centre[0] * scale * factor, centre[1] * scale * factor
    arc_radius = radius * scale * factor
    box = (cx - arc_radius, cy - arc_radius, cx + arc_radius, cy + arc_radius)
    line_width = max(1, round(18 * scale * factor))
    pillow_start = (-start) % 360
    pillow_end = pillow_start + abs(span)
    _centred_arc(draw, box, pillow_start, pillow_end, track, line_width)

    ratio = min(1.0, max(0.0, value / maximum)) if maximum else 0.0
    if ratio > 0:
        _centred_arc(draw, box, pillow_start, pillow_start + abs(span) * ratio, colour, line_width)

    angle = math.radians(start + span * ratio)
    thumb_x = (centre[0] + radius * math.cos(angle)) * scale * factor
    thumb_y = (centre[1] - radius * math.sin(angle)) * scale * factor
    # Slightly overlap both sides of the 18 px arc. This fully hides the arc's
    # flat endpoint and leaves one clean circular drag handle.
    thumb_radius = 10 * scale * factor
    outline_width = max(1, round(4 * scale * factor))
    draw.ellipse(
        (
            thumb_x - thumb_radius,
            thumb_y - thumb_radius,
            thumb_x + thumb_radius,
            thumb_y + thumb_radius,
        ),
        fill="white",
        outline=colour,
        width=outline_width,
    )
    return _finish(image, width, height)


def level_meter(width: int, height: int, scale: float, level: float, *, background: str, track: str, colour: str) -> Image.Image:
    width, height = _size(width, height)
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (width * factor, height * factor), background)
    draw = ImageDraw.Draw(image)
    inset = max(1, round(scale)) * factor
    left, right = inset, width * factor - inset - 1
    top, bottom = 2 * scale * factor, 16 * scale * factor
    _capsule(draw, left, top, right, bottom, track)

    level = min(1.0, max(0.0, level))
    if level > 0.0:
        progress_right = round(left + (right - left) * level)
        _capsule(draw, left, top, progress_right, bottom, colour)
    return _finish(image, width, height)


def status_dot(size: int, scale: float, *, background: str, colour: str) -> Image.Image:
    size = max(1, int(size))
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (size * factor, size * factor), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse(tuple(value * scale * factor for value in (2, 2, 10, 10)), fill=colour)
    return _finish(image, size, size)
