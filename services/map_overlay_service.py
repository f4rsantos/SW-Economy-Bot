import asyncio
import hashlib
import io
import json
import math
import os
import sys
from typing import Optional

import httpx
from PIL import Image, ImageDraw


_APP_ROOT = getattr(sys, "_MEIPASS", os.getcwd())

BACKGROUND_CACHE_DIR = os.getenv("MAP_BACKGROUND_CACHE_DIR", os.path.join("data", "map_background_cache"))
LOCAL_BACKGROUND_DIR = os.getenv("MAP_BACKGROUND_DIR", os.path.join(_APP_ROOT, "map-backgrounds"))
LOCAL_BACKGROUND_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

HEX_SIZE = 25
HEX_APOTHEM = math.sqrt(3) * HEX_SIZE / 2
COL_WIDTH = HEX_SIZE * 1.5
ROW_HEIGHT = HEX_APOTHEM * 2
GRID_OFFSET_X = HEX_SIZE / 2


FIREBASE_PROJECT_ID = os.getenv("MAP_FIREBASE_PROJECT_ID", "solar-wars-maps")
FIREBASE_DOC_ROOT = os.getenv("MAP_FIREBASE_DOC_ROOT", "HMG")
FIREBASE_API_KEY = os.getenv("MAP_FIREBASE_API_KEY", "")


def _firestore_unwrap(value: dict):
    if not isinstance(value, dict):
        return value
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [_firestore_unwrap(v) for v in values]
    if "mapValue" in value:
        fields = value["mapValue"].get("fields", {})
        return {k: _firestore_unwrap(v) for k, v in fields.items()}
    return value


def _parse_editor_overlay(raw: dict, defaults: Optional[dict] = None) -> dict:
    defaults = defaults if isinstance(defaults, dict) else {}

    if isinstance(raw, dict) and "overlay" in raw and isinstance(raw["overlay"], dict):
        overlay = raw["overlay"]
    else:
        overlay = raw

    factions = overlay.get("factions", [])
    hexes = overlay.get("hexes", [])
    width = int(overlay.get("width", len(hexes) if hexes else 0))
    if width <= 0:
        width = len(hexes)
    height = int(overlay.get("height", len(hexes[0]) if hexes and isinstance(hexes[0], list) else 0))

    stroke = overlay.get("stroke") or defaults.get("stroke") or {"r": 255, "g": 255, "b": 255, "a": 0.3}
    hex_opacity = float(overlay.get("hexOpacity", defaults.get("hexOpacity", 0.6)))
    image_cfg = overlay.get("image", {}) if isinstance(overlay.get("image"), dict) else {}
    default_image_cfg = defaults.get("image", {}) if isinstance(defaults.get("image"), dict) else {}

    image_scale_x = image_cfg.get("scaleX", default_image_cfg.get("scaleX", 1.0))
    image_scale_y = image_cfg.get("scaleY", default_image_cfg.get("scaleY", 1.0))

    return {
        "width": width,
        "height": height,
        "factions": factions,
        "hexes": hexes,
        "stroke": stroke,
        "hex_opacity": hex_opacity,
        "image_scale_x": float(image_scale_x),
        "image_scale_y": float(image_scale_y),
    }


async def fetch_world_map_config(world_name: str) -> Optional[dict]:
    world_key = world_name.strip()
    world_key_lower = world_key.lower()

    urls = [
        f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/mapConfigs/{FIREBASE_DOC_ROOT}",
        f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/maps/{FIREBASE_DOC_ROOT}",
        f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIREBASE_DOC_ROOT}/{world_key_lower}",
        f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIREBASE_DOC_ROOT}/{world_key}",
    ]

    params = {"key": FIREBASE_API_KEY} if FIREBASE_API_KEY else None

    async with httpx.AsyncClient(timeout=15) as client:
        for url in urls:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                doc = resp.json()
                fields = doc.get("fields", {})
                if not fields:
                    continue

                world_field = None
                hmg_defaults = None
                for k, v in fields.items():
                    if k.lower() in {"defaults", "default", "hmgdefaults", "styledefaults"}:
                        unwrapped = _firestore_unwrap(v)
                        if isinstance(unwrapped, dict):
                            hmg_defaults = unwrapped
                    if k.lower() == world_key_lower:
                        world_field = _firestore_unwrap(v)
                        break
                if isinstance(world_field, dict):
                    if isinstance(hmg_defaults, dict):
                        world_field["_hmg_defaults"] = hmg_defaults
                    return world_field

                normalized = {k: _firestore_unwrap(v) for k, v in fields.items()}
                if "background" in normalized or "overlay" in normalized:
                    return normalized
            except Exception:
                continue

    return None


async def _load_overlay_data(overlay_value) -> Optional[dict]:
    if isinstance(overlay_value, dict):
        return overlay_value
    if isinstance(overlay_value, str):
        stripped = overlay_value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return json.loads(stripped)
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                resp = await client.get(stripped)
                if resp.status_code != 404 or attempt == 2:
                    resp.raise_for_status()
                    break
                await asyncio.sleep(1)
            return resp.json()
    return None


def _hex_points(cx: float, cy: float) -> list[tuple[float, float]]:
    points = []
    for i in range(6):
        angle = (math.pi / 3) * i
        x = cx + HEX_SIZE * math.cos(angle)
        y = cy + HEX_SIZE * math.sin(angle)
        points.append((x, y))
    return points


def _edge_key(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    a = (round(p1[0], 4), round(p1[1], 4))
    b = (round(p2[0], 4), round(p2[1], 4))
    return (a, b) if a <= b else (b, a)


def _hex_center(q: int, r: int) -> tuple[float, float]:
    cx = q * COL_WIDTH + GRID_OFFSET_X
    cy = r * ROW_HEIGHT
    if q % 2 != 0:
        cy += HEX_APOTHEM
    return cx, cy


def _editor_grid_size(width: int, height: int) -> tuple[float, float]:
    grid_width = max(1.0, (max(width, 1) - 1) * COL_WIDTH + HEX_SIZE)
    grid_height = max(1.0, (max(height, 1) - 1) * ROW_HEIGHT + HEX_APOTHEM)
    return grid_width, grid_height


def _target_canvas_size(width: int, height: int) -> tuple[int, int]:
    map_width = max(1.0, width * COL_WIDTH + HEX_SIZE * 2 + GRID_OFFSET_X)
    map_height = max(1.0, height * ROW_HEIGHT + HEX_APOTHEM * 2)
    return int(math.ceil(map_width)), int(math.ceil(map_height))


def _background_cache_path(background_url: str) -> str:
    key = hashlib.sha256(background_url.encode("utf-8")).hexdigest()
    return os.path.join(BACKGROUND_CACHE_DIR, f"{key}.bin")


def _local_background_path(world_name: Optional[str]) -> Optional[str]:
    if not world_name:
        return None
    candidates = {world_name, world_name.replace(" ", "")}
    for name in candidates:
        for ext in LOCAL_BACKGROUND_EXTS:
            path = os.path.join(LOCAL_BACKGROUND_DIR, f"{name}{ext}")
            if os.path.exists(path):
                return path
    return None


async def _fetch_background_bytes(background_url: str, world_name: Optional[str] = None) -> bytes:
    local_path = _local_background_path(world_name)
    if local_path:
        with open(local_path, "rb") as f:
            return f.read()

    cache_path = _background_cache_path(background_url)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read()

    async with httpx.AsyncClient(timeout=25) as client:
        for attempt in range(3):
            bg_resp = await client.get(background_url)
            if bg_resp.status_code != 404 or attempt == 2:
                bg_resp.raise_for_status()
                break
            await asyncio.sleep(1)

    os.makedirs(BACKGROUND_CACHE_DIR, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(bg_resp.content)
    return bg_resp.content


async def render_world_overlay_image(background_url: str, overlay_raw, defaults: Optional[dict] = None, world_name: Optional[str] = None) -> bytes:
    background_bytes = await _fetch_background_bytes(background_url, world_name)
    original_bg = Image.open(io.BytesIO(background_bytes)).convert("RGBA")

    overlay_data = await _load_overlay_data(overlay_raw)
    if not isinstance(overlay_data, dict):
        raise ValueError("Overlay must be a JSON object (or URL returning one).")

    parsed = _parse_editor_overlay(overlay_data, defaults=defaults)
    width = int(parsed.get("width", 0))
    height = int(parsed.get("height", 0))
    factions = parsed["factions"]
    hexes = parsed["hexes"]
    hex_opacity_alpha = 153

    has_claimed_hexes = any(
        isinstance(col, list) and any(cell is not None for cell in col)
        for col in hexes
    )
    if not has_claimed_hexes:
        output = io.BytesIO()
        original_bg.save(output, format="PNG")
        return output.getvalue()

    grid_width, grid_height = _editor_grid_size(width, height)
    scale_x = grid_width / max(1, original_bg.width)
    scale_y = grid_height / max(1, original_bg.height)

    exported_scale_x = float(parsed.get("image_scale_x", 1.0))
    exported_scale_y = float(parsed.get("image_scale_y", 1.0))
    if exported_scale_x > 0:
        scale_x = exported_scale_x
    if exported_scale_y > 0:
        scale_y = exported_scale_y

    resized_bg_w = max(1, int(round(original_bg.width * scale_x)))
    resized_bg_h = max(1, int(round(original_bg.height * scale_y)))
    resized_bg = original_bg.resize((resized_bg_w, resized_bg_h), Image.Resampling.LANCZOS)

    canvas_w, canvas_h = _target_canvas_size(width, height)
    canvas_w = max(canvas_w, resized_bg_w)
    canvas_h = max(canvas_h, resized_bg_h)

    base = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    base.paste(resized_bg, (0, 0))
    overlay_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer, "RGBA")

    faction_colors = {}
    for f in factions:
        fill = f.get("fill")
        if isinstance(fill, str):
            c = fill if fill.startswith("#") else f"#{fill}"
            faction_colors[f.get("id")] = c

    stroke_rgba = (170, 170, 170, 255)
    unique_edges: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for q, col in enumerate(hexes):
        if not isinstance(col, list):
            continue
        for r, faction_id in enumerate(col):
            if faction_id is None:
                continue
            color_hex = faction_colors.get(faction_id)
            if not color_hex:
                continue
            color_hex = color_hex.lstrip("#")
            if len(color_hex) != 6:
                continue

            fill_rgba = (
                int(color_hex[0:2], 16),
                int(color_hex[2:4], 16),
                int(color_hex[4:6], 16),
                hex_opacity_alpha,
            )

            cx, cy = _hex_center(q, r)
            points = _hex_points(cx, cy)
            draw.polygon(points, fill=fill_rgba)
            for i in range(6):
                p1 = points[i]
                p2 = points[(i + 1) % 6]
                unique_edges.add(_edge_key(p1, p2))

    for p1, p2 in unique_edges:
        draw.line([p1, p2], fill=stroke_rgba, width=2)

    base = Image.alpha_composite(base, overlay_layer)

    output = io.BytesIO()
    base.save(output, format="PNG")
    return output.getvalue()
