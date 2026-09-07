from __future__ import annotations

import math

from PIL import Image, ImageDraw


SUPERSAMPLE = 4


def _size(width: int, height: int) -> tuple[int, int]:
    return max(1, int(width)), max(1, int(height))


def _finish(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.resize(_size(width, height), Image.Resampling.LANCZOS)


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
    thumb_radius = 8 * scale * factor
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
    top, bottom = 4 * scale * factor, 14 * scale * factor
    radius = 5 * scale * factor
    draw.rounded_rectangle((0, top, width * factor, bottom), radius=radius, fill=track)
    progress = width * min(1.0, max(0.0, level)) * factor
    if progress > 0:
        draw.rounded_rectangle((0, top, progress, bottom), radius=radius, fill=colour)
    return _finish(image, width, height)


def arc_logo(size: int, scale: float, *, background: str, accent: str) -> Image.Image:
    size = max(1, int(size))
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (size * factor, size * factor), background)
    draw = ImageDraw.Draw(image)

    def box(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        return tuple(value * scale * factor for value in values)

    # Tk starts at 38 degrees above the x-axis and sweeps counter-clockwise.
    # Pillow's angles grow clockwise in screen coordinates, so -38 is the
    # matching starting point and the 285-degree sweep can stay positive.
    _centred_arc(draw, box((4, 4, 42, 42)), 322, 607, accent, round(5 * scale * factor))
    _centred_arc(draw, box((12, 12, 34, 34)), 322, 607, "#A8B5FF", round(5 * scale * factor))
    draw.ellipse(box((19, 19, 27, 27)), fill=accent)
    return _finish(image, size, size)


def status_dot(size: int, scale: float, *, background: str, colour: str) -> Image.Image:
    size = max(1, int(size))
    factor = SUPERSAMPLE
    image = Image.new("RGBA", (size * factor, size * factor), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse(tuple(value * scale * factor for value in (2, 2, 10, 10)), fill=colour)
    return _finish(image, size, size)
