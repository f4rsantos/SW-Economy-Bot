# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io

from PIL import Image, ImageDraw, ImageFont

MASK32 = 0xFFFFFFFF

HUE_GROUPS = [
    ["#c62828", "#e53935", "#ff1744"],
    ["#e65100", "#f57c00", "#ff6d00"],
    ["#f9a825", "#fdd835"],
    ["#1b5e20", "#43a047", "#00c853"],
    ["#006064", "#00acc1", "#00e5ff"],
    ["#0d47a1", "#1e88e5", "#2979ff"],
    ["#4a148c", "#8e24aa", "#d500f9"],
    ["#880e4f", "#e91e63"],
    ["#ffffff", "#cfd8dc", "#b0bec5"],
]

FOUR_COLOR_IDS = {2, 3, 4, 5, 6, 7, 10}

RIBBON_WIDTH = 72
RIBBON_HEIGHT = 14
DEFAULT_SCALE = 4


def imul32(a: int, b: int) -> int:
    return (a * b) & MASK32


def hash32(n: int) -> int:
    n = (n ^ 0xdeadbeef) & MASK32
    n = imul32(n ^ (n >> 16), 0x45d9f3b)
    n = imul32(n ^ (n >> 16), 0xd3a2646c)
    n = (n ^ (n >> 16)) & MASK32
    return n


def pick_distinct_groups(badge_id: int, count: int) -> list[int]:
    total = len(HUE_GROUPS)
    pool = list(range(total))
    seed = hash32(badge_id)
    for i in range(total - 1, 0, -1):
        seed = hash32(seed ^ i)
        j = seed % (i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return pool[:count]


def pick_from_group(group_idx: int, badge_id: int, slot: int) -> str:
    group = HUE_GROUPS[group_idx]
    idx = hash32(badge_id ^ hash32(imul32(slot, 0xf1234567))) % len(group)
    return group[idx]


def band_weight(badge_id: int, slot: int, range_: int, min_: int) -> int:
    return (hash32(badge_id ^ hash32(imul32(slot, 0xc1234567))) % range_) + min_


def band_spec(badge_id: int) -> list[dict]:
    use_four = badge_id in FOUR_COLOR_IDS
    color_count = 4 if use_four else 3
    groups = pick_distinct_groups(badge_id, color_count)
    colors = [pick_from_group(g, badge_id, i) for i, g in enumerate(groups)]

    if use_four:
        a, b, c, d = colors
        return [
            {"color": a, "weight": band_weight(badge_id, 1, 4, 3)},
            {"color": b, "weight": band_weight(badge_id, 2, 6, 5)},
            {"color": c, "weight": band_weight(badge_id, 3, 4, 3)},
            {"color": d, "weight": band_weight(badge_id, 4, 6, 8)},
            {"color": c, "weight": band_weight(badge_id, 3, 4, 3)},
            {"color": b, "weight": band_weight(badge_id, 2, 6, 5)},
            {"color": a, "weight": band_weight(badge_id, 1, 4, 3)},
        ]

    a, b, c = colors
    if hash32(badge_id ^ 0xabcdef) % 2 == 0:
        return [
            {"color": a, "weight": band_weight(badge_id, 1, 6, 3)},
            {"color": b, "weight": band_weight(badge_id, 2, 4, 2)},
            {"color": c, "weight": band_weight(badge_id, 3, 8, 6)},
            {"color": b, "weight": band_weight(badge_id, 2, 4, 2)},
            {"color": a, "weight": band_weight(badge_id, 1, 6, 3)},
        ]
    return [
        {"color": a, "weight": band_weight(badge_id, 1, 8, 6)},
        {"color": b, "weight": band_weight(badge_id, 2, 4, 2)},
        {"color": c, "weight": band_weight(badge_id, 3, 5, 3)},
        {"color": b, "weight": band_weight(badge_id, 2, 4, 2)},
        {"color": a, "weight": band_weight(badge_id, 1, 8, 6)},
    ]


def compute_widths(bands: list[dict], total: int) -> list[int]:
    min_px = -(-total // 10)
    band_sum = sum(b["weight"] for b in bands)
    widths = [max(min_px, (b["weight"] * total) // band_sum) for b in bands]
    actual = sum(widths)
    diff = total - actual
    widths[len(widths) // 2] += diff
    return widths


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def render_ribbon_png(badge_id: int, scale: int = DEFAULT_SCALE) -> bytes:
    width = RIBBON_WIDTH * scale
    height = RIBBON_HEIGHT * scale

    bands = band_spec(badge_id)
    widths = compute_widths(bands, width)

    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    x = 0
    for band, band_width in zip(bands, widths):
        if band_width <= 0:
            continue
        draw.rectangle([x, 0, x + band_width - 1, height - 1], fill=_hex_to_rgb(band["color"]))
        x += band_width

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_ribbon_stack_png(badge_ids: list[int], scale: int = DEFAULT_SCALE, gap: int = 4) -> bytes:
    width = RIBBON_WIDTH * scale
    ribbon_height = RIBBON_HEIGHT * scale
    gap_px = gap * scale
    count = len(badge_ids)
    total_height = ribbon_height * count + gap_px * max(count - 1, 0)

    stacked = Image.new("RGB", (width, total_height), (0, 0, 0))
    y = 0
    for badge_id in badge_ids:
        ribbon_bytes = render_ribbon_png(badge_id, scale=scale)
        ribbon_image = Image.open(io.BytesIO(ribbon_bytes))
        stacked.paste(ribbon_image, (0, y))
        y += ribbon_height + gap_px

    buffer = io.BytesIO()
    stacked.save(buffer, format="PNG")
    return buffer.getvalue()


GRID_TRUETYPE_CANDIDATES = ["segoeui.ttf", "arial.ttf"]

GRID_FEW_BADGES_COLUMNS = 2
GRID_MANY_BADGES_COLUMNS = 3
GRID_MANY_BADGES_THRESHOLD = 5

GRID_CELL_PAD_X = 10
GRID_CELL_PAD_Y = 8
GRID_LABEL_GAP = 4
GRID_LABEL_LINE_HEIGHT = 16
GRID_LABEL_MAX_LINES = 2
GRID_FONT_SIZE = 13
GRID_TEXT_COLOR = (230, 230, 230)
GRID_BACKGROUND = (0, 0, 0)


def choose_grid_columns(badge_count: int) -> int:
    if badge_count <= 0:
        return 0
    if badge_count < GRID_MANY_BADGES_THRESHOLD:
        return GRID_FEW_BADGES_COLUMNS
    return GRID_MANY_BADGES_COLUMNS


def load_grid_font(size: int = GRID_FONT_SIZE) -> ImageFont.FreeTypeFont:
    for name in GRID_TRUETYPE_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_label(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
    else:
        lines.append(current)
        return lines

    remaining_words = words[len(" ".join(lines).split()):]
    remainder = " ".join(remaining_words) if remaining_words else current
    while remainder and draw.textlength(remainder, font=font) > max_width:
        remainder = remainder[:-1]
    ellipsis = "..."
    while remainder and draw.textlength(remainder + ellipsis, font=font) > max_width:
        remainder = remainder[:-1]
    lines.append(f"{remainder}{ellipsis}" if remainder else ellipsis)
    return lines[:max_lines]


def _build_badge_grid_image(
    badges: list[tuple[int, str]],
    columns: int = None,
    scale: int = DEFAULT_SCALE,
) -> Image.Image:
    count = len(badges)
    if count == 0:
        raise ValueError("render_badge_grid_png requires at least one badge")

    cols = columns if columns is not None else choose_grid_columns(count)
    cols = max(1, min(cols, count))
    rows = -(-count // cols)

    ribbon_width = RIBBON_WIDTH * scale
    ribbon_height = RIBBON_HEIGHT * scale
    pad_x = GRID_CELL_PAD_X * scale // DEFAULT_SCALE
    pad_y = GRID_CELL_PAD_Y * scale // DEFAULT_SCALE
    label_gap = GRID_LABEL_GAP * scale // DEFAULT_SCALE
    label_line_height = GRID_LABEL_LINE_HEIGHT * scale // DEFAULT_SCALE
    font_size = GRID_FONT_SIZE * scale // DEFAULT_SCALE

    cell_width = ribbon_width + pad_x * 2
    label_block_height = label_gap + label_line_height * GRID_LABEL_MAX_LINES
    cell_height = ribbon_height + label_block_height + pad_y * 2

    canvas_width = cell_width * cols
    canvas_height = cell_height * rows

    canvas = Image.new("RGB", (canvas_width, canvas_height), GRID_BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    font = load_grid_font(font_size)

    for index, (badge_id, name) in enumerate(badges):
        col = index % cols
        row = index // cols
        cell_x = col * cell_width
        cell_y = row * cell_height

        ribbon_bytes = render_ribbon_png(badge_id, scale=scale)
        ribbon_image = Image.open(io.BytesIO(ribbon_bytes))
        ribbon_x = cell_x + pad_x
        ribbon_y = cell_y + pad_y
        canvas.paste(ribbon_image, (ribbon_x, ribbon_y))

        label_max_width = ribbon_width + pad_x
        lines = _wrap_label(draw, name, font, label_max_width, GRID_LABEL_MAX_LINES)

        text_y = ribbon_y + ribbon_height + label_gap
        for line in lines:
            line_width = draw.textlength(line, font=font)
            line_x = cell_x + (cell_width - line_width) / 2
            draw.text((line_x, text_y), line, font=font, fill=GRID_TEXT_COLOR)
            text_y += label_line_height

    return canvas


def render_badge_grid_png(
    badges: list[tuple[int, str]],
    columns: int = None,
    scale: int = DEFAULT_SCALE,
) -> bytes:
    canvas = _build_badge_grid_image(badges, columns=columns, scale=scale)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


CARD_BACKGROUND = (0, 0, 0)
CARD_PADDING = 16
CARD_DIVIDER_WIDTH = 2
CARD_DIVIDER_COLOR = (60, 60, 60)
CARD_AVATAR_SIZE = 160
CARD_AVATAR_PLACEHOLDER_COLOR = (40, 40, 40)
CARD_NAME_GAP = 10
CARD_NAME_FONT_SIZE = 20
CARD_TREATMENT_GAP = 4
CARD_TREATMENT_FONT_SIZE = 14
CARD_NAME_COLOR = (255, 255, 255)
CARD_TREATMENT_COLOR = (180, 180, 180)
CARD_NO_BADGES_FONT_SIZE = 15
CARD_NO_BADGES_COLOR = (150, 150, 150)


def render_user_card_png(
    avatar_bytes: bytes | None,
    name: str,
    treatment: str | None,
    badges: list[tuple[int, str]],
    columns: int = None,
    scale: int = DEFAULT_SCALE,
) -> bytes:
    pad = CARD_PADDING * scale // DEFAULT_SCALE
    avatar_size = CARD_AVATAR_SIZE * scale // DEFAULT_SCALE
    divider_width = max(1, CARD_DIVIDER_WIDTH * scale // DEFAULT_SCALE)
    name_gap = CARD_NAME_GAP * scale // DEFAULT_SCALE
    treatment_gap = CARD_TREATMENT_GAP * scale // DEFAULT_SCALE
    name_font_size = CARD_NAME_FONT_SIZE * scale // DEFAULT_SCALE
    treatment_font_size = CARD_TREATMENT_FONT_SIZE * scale // DEFAULT_SCALE
    no_badges_font_size = CARD_NO_BADGES_FONT_SIZE * scale // DEFAULT_SCALE

    name_font = load_grid_font(name_font_size)
    treatment_font = load_grid_font(treatment_font_size)

    avatar_image = None
    if avatar_bytes:
        try:
            opened = Image.open(io.BytesIO(avatar_bytes))
            opened = opened.convert("RGB")
            avatar_image = opened.resize((avatar_size, avatar_size))
        except Exception:
            avatar_image = None

    left_width = avatar_size + pad * 2
    left_content_height = avatar_size + name_gap + name_font_size + treatment_gap + treatment_font_size
    left_height = left_content_height + pad * 2

    if badges:
        grid_image = _build_badge_grid_image(badges, columns=columns, scale=scale)
        right_width = grid_image.width + pad * 2
        right_height = grid_image.height + pad * 2
    else:
        grid_image = None
        right_width = (RIBBON_WIDTH * scale) + pad * 2
        right_height = no_badges_font_size + pad * 2

    canvas_height = max(left_height, right_height)
    canvas_width = left_width + divider_width + right_width

    canvas = Image.new("RGB", (canvas_width, canvas_height), CARD_BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    avatar_x = pad
    avatar_y = pad
    if avatar_image is not None:
        canvas.paste(avatar_image, (avatar_x, avatar_y))
    else:
        draw.rectangle(
            [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
            fill=CARD_AVATAR_PLACEHOLDER_COLOR,
        )

    text_y = avatar_y + avatar_size + name_gap
    name_lines = _wrap_label(draw, name, name_font, avatar_size, 1)
    name_text = name_lines[0]
    name_width = draw.textlength(name_text, font=name_font)
    draw.text((avatar_x + (avatar_size - name_width) / 2, text_y), name_text, font=name_font, fill=CARD_NAME_COLOR)

    text_y += name_font_size + treatment_gap
    treatment_text = treatment or "None"
    treatment_lines = _wrap_label(draw, treatment_text, treatment_font, avatar_size, 1)
    treatment_display = treatment_lines[0]
    treatment_width = draw.textlength(treatment_display, font=treatment_font)
    draw.text(
        (avatar_x + (avatar_size - treatment_width) / 2, text_y),
        treatment_display,
        font=treatment_font,
        fill=CARD_TREATMENT_COLOR,
    )

    divider_x = left_width
    draw.rectangle([divider_x, 0, divider_x + divider_width - 1, canvas_height - 1], fill=CARD_DIVIDER_COLOR)

    right_x = left_width + divider_width + pad
    if grid_image is not None:
        canvas.paste(grid_image, (right_x, pad))
    else:
        no_badges_font = load_grid_font(no_badges_font_size)
        draw.text((right_x, pad), "No badges", font=no_badges_font, fill=CARD_NO_BADGES_COLOR)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
