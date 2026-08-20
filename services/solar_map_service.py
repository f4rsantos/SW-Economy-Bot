import io
import math
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

import services.orbital_config as config
from services.travel_time_service import get_absolute_position_3d, get_config_key
from services.orbital_config import IRL_SECONDS_PER_GAME_YEAR
from utils.date_utils import get_solar_date, is_leap_year


_APP_ROOT = getattr(sys, "_MEIPASS", os.getcwd())
WORLDS_DIR = os.getenv("WORLDS_DIR", os.path.join(_APP_ROOT, "worlds"))
PLACEHOLDER_ICON = os.path.join(WORLDS_DIR, "placeholder.png")

SOLAR_EPOCH = datetime(2023, 5, 1)
SOLAR_EPOCH_YEAR = 2123

SUPERSAMPLE = 2

BASE_SIZE = 1600
FOCUS_SIZE = 1400
MARGIN = 90

BG_TOP = (6, 8, 20)
BG_BOTTOM = (14, 12, 30)
ORBIT_COLOR = (90, 100, 130, 90)
SUN_GLOW = (255, 210, 120)
TEXT_COLOR = (225, 228, 240)
TEXT_SHADOW = (0, 0, 0)
SUBTLE_TEXT = (150, 155, 175)

PLANET_ICON_MIN = 26
PLANET_ICON_MAX = 64
MOON_ICON_MIN = 30
MOON_ICON_MAX = 60
BELT_DOT_RADIUS = 3

BODY_RADII_KM = {
    "Mercury": 2440, "Venus": 6052, "Earth": 6371, "Mars": 3390,
    "Jupiter": 69911, "Saturn": 58232, "Uranus": 25362, "Neptune": 24622,
    "Pluto": 1188, "Ceres": 473,
    "Luna": 1737,
    "Io": 1822, "Europa": 1561, "Ganymede": 2634, "Callisto": 2410,
    "Mimas": 198, "Enceladus": 252, "Tethys": 531, "Dione": 561,
    "Rhea": 764, "Titan": 2575, "Iapetus": 735,
    "Miranda": 236, "Ariel": 579, "Umbriel": 585, "Titania": 789, "Oberon": 761,
    "Proteus": 210, "Triton": 1353, "Nereid": 170,
    "Charon": 606,
    "Barcas": 5800, "Deo Gloria": 4200, "Novai": 7100, "Scipios": 3100,
    "Vesta": 263,
}

DEFAULT_BODY_RADIUS_KM = 3000

FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeui.ttf"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_BOLD_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeuib.ttf"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

_icon_cache = {}
_font_cache = {}


class SolarMapError(ValueError):
    pass


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES
    font = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def resolve_system(system_name: str) -> tuple[str, dict]:
    for key in config.SYSTEMS_DATA:
        if key.lower() == system_name.strip().lower():
            return key, config.SYSTEMS_DATA[key]
    raise SolarMapError(f"Unknown system '{system_name}'. Valid systems: {', '.join(config.SYSTEMS_DATA.keys())}")


def resolve_body(body_name: str, system_data: dict) -> str:
    key = get_config_key(body_name, system_data)
    if not key:
        raise SolarMapError(f"Unknown body '{body_name}' in this system.")
    return key


def parse_game_date(date_str: str) -> datetime:
    parts = date_str.strip().split("-")
    if len(parts) != 3:
        raise SolarMapError(f"Invalid date '{date_str}'. Use format yyyy-mm-dd (in-game date).")
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise SolarMapError(f"Invalid date '{date_str}'. Use format yyyy-mm-dd (in-game date).")
    if not (1 <= month <= 12):
        raise SolarMapError(f"Invalid month '{month}'. Must be between 1 and 12.")
    if day < 1 or day > 31:
        raise SolarMapError(f"Invalid day '{day}'. Must be between 1 and 31.")
    return _solar_to_real(year, month, day)


def _solar_to_real(year: int, month: int, day: int) -> datetime:
    total_months = year - SOLAR_EPOCH_YEAR
    real_month_index = (SOLAR_EPOCH.month - 1) + total_months
    real_year = SOLAR_EPOCH.year + real_month_index // 12
    real_month = real_month_index % 12 + 1

    month_start = datetime(real_year, real_month, 1)
    month_end = datetime(real_year + 1, 1, 1) if real_month == 12 else datetime(real_year, real_month + 1, 1)
    year_len = (month_end - month_start).total_seconds() - 1

    leap = is_leap_year(year)
    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if leap:
        months[1] = 29
    if month > 12 or day > months[month - 1]:
        raise SolarMapError(f"Invalid day '{day}' for month '{month}'.")

    day_count = sum(months[: month - 1]) + day
    days_in_year = 366 if leap else 365
    fraction = min((day_count + 0.5) / days_in_year, 1.0)
    point_seconds = fraction * year_len
    return month_start + timedelta(seconds=point_seconds)


def current_game_date_str(now: Optional[datetime] = None) -> str:
    year, month, day = get_solar_date(now)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _icon_path(body_name: str) -> str:
    candidate = os.path.join(WORLDS_DIR, f"{body_name}.png")
    return candidate if os.path.exists(candidate) else PLACEHOLDER_ICON


def _load_icon(body_name: str, target_size: int) -> Image.Image:
    key = (body_name, target_size)
    if key in _icon_cache:
        return _icon_cache[key]
    path = _icon_path(body_name)
    icon = Image.open(path).convert("RGBA")
    icon = icon.resize((target_size, target_size), Image.LANCZOS)
    _icon_cache[key] = icon
    return icon


def _is_top_level(name: str, data: dict) -> bool:
    return data.get("parent") is None


def _radius_scale_for_bodies(bodies: list[str], system_data: dict) -> dict:
    if not bodies:
        return {}
    radii = [BODY_RADII_KM.get(b, DEFAULT_BODY_RADIUS_KM) for b in bodies]
    min_r, max_r = min(radii), max(radii)
    scale = {}
    for b in bodies:
        r = BODY_RADII_KM.get(b, DEFAULT_BODY_RADIUS_KM)
        if max_r > min_r:
            t = (math.log(r) - math.log(min_r)) / (math.log(max_r) - math.log(min_r))
        else:
            t = 0.5
        scale[b] = t
    return scale


def _icon_size_for(t: float, is_moon: bool = False) -> int:
    lo, hi = (MOON_ICON_MIN, MOON_ICON_MAX) if is_moon else (PLANET_ICON_MIN, PLANET_ICON_MAX)
    return int(lo + (hi - lo) * t)


def _draw_orbit_path(draw: ImageDraw.Draw, cx: float, cy: float, points: list):
    if len(points) < 2:
        return
    draw.line(points + [points[0]], fill=ORBIT_COLOR, width=2, joint="curve")


def _orbit_points(name: str, system_data: dict, when: datetime, radius_px, center: float, relative_to: str = None, samples: int = 240) -> list:
    data = system_data[name]
    period_years = data.get("period", 0) or 0
    if period_years <= 0:
        return []
    period_seconds = period_years * IRL_SECONDS_PER_GAME_YEAR
    points = []
    for i in range(samples):
        t = when + timedelta(seconds=period_seconds * (i / samples))
        pos = get_absolute_position_3d(name, t, system_data)
        px, py = pos.x, pos.y
        if relative_to:
            parent = get_absolute_position_3d(relative_to, t, system_data)
            px, py = px - parent.x, py - parent.y
        d = math.hypot(px, py)
        angle = math.atan2(py, px)
        r = radius_px(d)
        points.append((center + r * math.cos(angle), center + r * math.sin(angle)))
    return points


def _draw_gradient_background(size: int) -> Image.Image:
    img = Image.new("RGB", (1, size), BG_TOP)
    top = BG_TOP
    bottom = BG_BOTTOM
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        img.putpixel((0, y), (r, g, b))
    return img.resize((size, size))


def _draw_sun(image: Image.Image, cx: float, cy: float, radius: float):
    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_layer, "RGBA")
    for i in range(6, 0, -1):
        alpha = int(28 * (i / 6))
        r = radius * (1 + i * 0.4)
        gdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*SUN_GLOW, alpha))
    image.alpha_composite(glow_layer)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(255, 236, 180))
    draw.ellipse([cx - radius * 0.7, cy - radius * 0.7, cx + radius * 0.7, cy + radius * 0.7], fill=(255, 250, 220))


def _text_with_shadow(draw: ImageDraw.Draw, xy, text: str, font, fill=TEXT_COLOR, anchor="ma"):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=font, fill=TEXT_SHADOW, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def _place_label(placed_boxes: list, x: float, y: float, w: float, h: float, preferred_offsets: list) -> tuple[float, float]:
    for ox, oy in preferred_offsets:
        cand = (x + ox - w / 2, y + oy - h / 2, x + ox + w / 2, y + oy + h / 2)
        overlap = False
        for box in placed_boxes:
            if not (cand[2] < box[0] or cand[0] > box[2] or cand[3] < box[1] or cand[1] > box[3]):
                overlap = True
                break
        if not overlap:
            placed_boxes.append(cand)
            return x + ox, y + oy
    ox, oy = preferred_offsets[-1]
    cand = (x + ox - w / 2, y + oy - h / 2, x + ox + w / 2, y + oy + h / 2)
    placed_boxes.append(cand)
    return x + ox, y + oy


def render_solar_map(
    system_name: str,
    date_str: Optional[str] = None,
    mode: str = "log",
    zoom: float = 1.0,
    focus: Optional[str] = None,
) -> tuple[bytes, str, str]:
    canonical_system, system_data = resolve_system(system_name)

    if date_str:
        when = parse_game_date(date_str)
        game_date_label = date_str
    else:
        when = datetime.now()
        game_date_label = current_game_date_str(when)

    mode = (mode or "log").lower()
    if mode not in ("log", "linear"):
        raise SolarMapError("Mode must be 'log' or 'linear'.")

    zoom = max(0.1, min(zoom or 1.0, 20.0))

    if focus:
        canonical_focus = resolve_body(focus, system_data)
        image_bytes = _render_focus(canonical_system, system_data, canonical_focus, when, zoom)
        title = f"{canonical_focus} System"
    else:
        image_bytes = _render_overview(canonical_system, system_data, when, mode, zoom)
        title = f"{canonical_system} System"

    return image_bytes, title, game_date_label


def _render_overview(system_name: str, system_data: dict, when: datetime, mode: str, zoom: float) -> bytes:
    size = BASE_SIZE * SUPERSAMPLE
    center = size / 2
    max_radius_px = center - MARGIN * SUPERSAMPLE

    bodies = [name for name, data in system_data.items() if _is_top_level(name, data)]
    positions = {}
    for name in bodies:
        pos = get_absolute_position_3d(name, when, system_data)
        positions[name] = pos

    dists = {name: math.hypot(positions[name].x, positions[name].y) for name in bodies}
    max_dist = max(dists.values()) if dists else 1.0
    min_dist = min((d for d in dists.values() if d > 1e-6), default=0.1)

    if mode == "log":
        min_radius_px = 90 * SUPERSAMPLE

        def radius_px(d):
            d = max(d, min_dist)
            t = (math.log(d) - math.log(min_dist)) / (math.log(max_dist) - math.log(min_dist)) if max_dist > min_dist else 0.0
            return min_radius_px + (max_radius_px - min_radius_px) * t
    else:
        px_per_au = (max_radius_px / max_dist) * zoom if max_dist > 0 else 1.0

        def radius_px(d):
            return d * px_per_au

    size_scale = _radius_scale_for_bodies(bodies, system_data)

    bg = _draw_gradient_background(size).convert("RGBA")
    draw = ImageDraw.Draw(bg, "RGBA")

    for name in bodies:
        _draw_orbit_path(draw, center, center, _orbit_points(name, system_data, when, radius_px, center))

    sun_radius = 24 * SUPERSAMPLE
    _draw_sun(bg, center, center, sun_radius)
    draw = ImageDraw.Draw(bg, "RGBA")

    font = _load_font(15 * SUPERSAMPLE)
    font_small = _load_font(12 * SUPERSAMPLE)
    _text_with_shadow(draw, (center, center + sun_radius + 6 * SUPERSAMPLE), "Sun" if system_name == "Sol" else system_name, font, anchor="ma")

    sun_box = (center - sun_radius, center - sun_radius, center + sun_radius, center + sun_radius * 2.2)
    placed_boxes: list = [sun_box]
    icon_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    render_order = sorted(bodies, key=lambda n: -dists[n])
    body_plots = {}
    for name in render_order:
        pos = positions[name]
        angle = math.atan2(pos.y, pos.x)
        r_px = radius_px(dists[name])
        x = center + r_px * math.cos(angle)
        y = center + r_px * math.sin(angle)
        body_plots[name] = (x, y)

        is_belt = "Asteroid Belt" in name
        if is_belt:
            continue

        t = size_scale.get(name, 0.5)
        icon_size = _icon_size_for(t) * SUPERSAMPLE
        icon = _load_icon(name, icon_size)
        icon_layer.paste(icon, (int(x - icon_size / 2), int(y - icon_size / 2)), icon)
        placed_boxes.append((x - icon_size / 2, y - icon_size / 2, x + icon_size / 2, y + icon_size / 2))

    for name in render_order:
        x, y = body_plots[name]
        is_belt = "Asteroid Belt" in name
        if is_belt:
            dot_r = BELT_DOT_RADIUS * SUPERSAMPLE
            draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=(170, 165, 150, 220))
            belt_label = name.replace("Asteroid Belt Area ", "Belt ")
            bbox = font_small.getbbox(belt_label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            belt_offsets = [
                (0, dot_r + th / 2 + 10 * SUPERSAMPLE),
                (0, -(dot_r + th / 2 + 10 * SUPERSAMPLE)),
                (dot_r + tw / 2 + 10 * SUPERSAMPLE, 0),
                (-(dot_r + tw / 2 + 10 * SUPERSAMPLE), 0),
            ]
            lx, ly = _place_label(placed_boxes, x, y, tw + 8 * SUPERSAMPLE, th + 8 * SUPERSAMPLE, belt_offsets)
            _text_with_shadow(draw, (lx, ly), belt_label, font_small, fill=SUBTLE_TEXT, anchor="mm")
            continue

        t = size_scale.get(name, 0.5)
        icon_size = _icon_size_for(t) * SUPERSAMPLE

        label = name
        bbox = font.getbbox(label)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        offsets = [
            (0, icon_size / 2 + 14 * SUPERSAMPLE),
            (0, -(icon_size / 2 + 14 * SUPERSAMPLE)),
            (icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE, 0),
            (-(icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE), 0),
            (icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE, icon_size / 2 + 10 * SUPERSAMPLE),
            (-(icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE), icon_size / 2 + 10 * SUPERSAMPLE),
            (icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE, -(icon_size / 2 + 10 * SUPERSAMPLE)),
            (-(icon_size / 2 + tw / 2 + 10 * SUPERSAMPLE), -(icon_size / 2 + 10 * SUPERSAMPLE)),
            (0, icon_size / 2 + 30 * SUPERSAMPLE),
            (0, -(icon_size / 2 + 30 * SUPERSAMPLE)),
        ]
        lx, ly = _place_label(placed_boxes, x, y, tw + 8 * SUPERSAMPLE, th + 8 * SUPERSAMPLE, offsets)
        _text_with_shadow(draw, (lx, ly), label, font, anchor="mm")

    bg = Image.alpha_composite(bg, icon_layer)
    draw = ImageDraw.Draw(bg, "RGBA")

    _text_with_shadow(draw, (24 * SUPERSAMPLE, size - 40 * SUPERSAMPLE), current_game_date_str(when), font_small, fill=SUBTLE_TEXT, anchor="lm")

    final = bg.resize((BASE_SIZE, BASE_SIZE), Image.LANCZOS)
    output = io.BytesIO()
    final.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def _render_focus(system_name: str, system_data: dict, focus_name: str, when: datetime, zoom: float) -> bytes:
    size = FOCUS_SIZE * SUPERSAMPLE
    center = size / 2
    max_radius_px = center - MARGIN * SUPERSAMPLE

    moons = [name for name, data in system_data.items() if data.get("parent") == focus_name]
    if not moons:
        raise SolarMapError(f"'{focus_name}' has no moons to display.")

    focus_pos = get_absolute_position_3d(focus_name, when, system_data)
    moon_positions = {}
    max_dist = 0.0
    min_dist = float("inf")
    for name in moons:
        pos = get_absolute_position_3d(name, when, system_data)
        rel_x, rel_y = pos.x - focus_pos.x, pos.y - focus_pos.y
        dist = math.hypot(rel_x, rel_y)
        moon_positions[name] = (rel_x, rel_y, dist)
        max_dist = max(max_dist, dist)
        if dist > 1e-9:
            min_dist = min(min_dist, dist)

    if max_dist <= 0:
        max_dist = 1.0
    if min_dist == float("inf"):
        min_dist = max_dist * 0.1

    size_scale = _radius_scale_for_bodies(list(system_data.keys()), system_data)
    planet_t = size_scale.get(focus_name, 0.6)
    planet_icon_size = int(_icon_size_for(planet_t) * 1.6) * SUPERSAMPLE
    inner_radius_px = max(90 * SUPERSAMPLE, planet_icon_size * 1.05)

    def moon_radius_px(dist):
        dist = max(dist, min_dist)
        if max_dist > min_dist:
            t = (math.log(dist) - math.log(min_dist)) / (math.log(max_dist) - math.log(min_dist))
        else:
            t = 1.0
        return (inner_radius_px + (max_radius_px - inner_radius_px) * t) * zoom

    bg = _draw_gradient_background(size).convert("RGBA")
    draw = ImageDraw.Draw(bg, "RGBA")

    for name in moons:
        _draw_orbit_path(draw, center, center, _orbit_points(name, system_data, when, lambda d: min(moon_radius_px(d), max_radius_px), center, relative_to=focus_name))

    icon_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    planet_icon = _load_icon(focus_name, planet_icon_size)
    icon_layer.paste(planet_icon, (int(center - planet_icon_size / 2), int(center - planet_icon_size / 2)), planet_icon)

    font = _load_font(15 * SUPERSAMPLE)
    font_small = _load_font(12 * SUPERSAMPLE)
    placed_boxes: list = [
        (center - planet_icon_size / 2, center - planet_icon_size / 2, center + planet_icon_size / 2, center + planet_icon_size / 2 + 40 * SUPERSAMPLE)
    ]
    _text_with_shadow(draw, (center, center + planet_icon_size / 2 + 6 * SUPERSAMPLE), focus_name, font, anchor="ma")

    render_order = sorted(moons, key=lambda n: -moon_positions[n][2])
    moon_plots = {}
    for name in render_order:
        rel_x, rel_y, dist = moon_positions[name]
        angle = math.atan2(rel_y, rel_x)
        r_px = min(moon_radius_px(dist), max_radius_px)
        x = center + r_px * math.cos(angle)
        y = center + r_px * math.sin(angle)
        moon_plots[name] = (x, y)

        icon_size = _icon_size_for(0.5, is_moon=True) * SUPERSAMPLE
        icon = _load_icon(name, icon_size)
        icon_layer.paste(icon, (int(x - icon_size / 2), int(y - icon_size / 2)), icon)
        placed_boxes.append((x - icon_size / 2, y - icon_size / 2, x + icon_size / 2, y + icon_size / 2))

    for name in render_order:
        x, y = moon_plots[name]
        icon_size = _icon_size_for(0.5, is_moon=True) * SUPERSAMPLE

        label = name
        bbox = font_small.getbbox(label)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        offsets = [
            (0, icon_size / 2 + 12 * SUPERSAMPLE),
            (0, -(icon_size / 2 + 12 * SUPERSAMPLE)),
            (icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE, 0),
            (-(icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE), 0),
            (icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE, icon_size / 2 + 8 * SUPERSAMPLE),
            (-(icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE), icon_size / 2 + 8 * SUPERSAMPLE),
            (icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE, -(icon_size / 2 + 8 * SUPERSAMPLE)),
            (-(icon_size / 2 + tw / 2 + 8 * SUPERSAMPLE), -(icon_size / 2 + 8 * SUPERSAMPLE)),
            (0, icon_size / 2 + 26 * SUPERSAMPLE),
            (0, -(icon_size / 2 + 26 * SUPERSAMPLE)),
        ]
        lx, ly = _place_label(placed_boxes, x, y, tw + 8 * SUPERSAMPLE, th + 8 * SUPERSAMPLE, offsets)
        _text_with_shadow(draw, (lx, ly), label, font_small, anchor="mm")

    bg = Image.alpha_composite(bg, icon_layer)
    draw = ImageDraw.Draw(bg, "RGBA")
    _text_with_shadow(draw, (24 * SUPERSAMPLE, size - 40 * SUPERSAMPLE), current_game_date_str(when), font_small, fill=SUBTLE_TEXT, anchor="lm")

    final = bg.resize((FOCUS_SIZE, FOCUS_SIZE), Image.LANCZOS)
    output = io.BytesIO()
    final.convert("RGB").save(output, format="PNG")
    return output.getvalue()
