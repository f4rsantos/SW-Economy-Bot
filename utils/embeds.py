import discord
from datetime import datetime, timezone
from typing import Optional
from database.cache_manager import cache
from database.db_manager import db

def create_embed(
    title: str,
    description: str = None,
    color: int = None,
    faction_id: int = None,
    fields: list = None,
    footer: str = None,
    thumbnail: str = None,
    image: str = None,
    user_id: int = None
) -> discord.Embed:
    if faction_id and not color:
        faction = cache.get_faction(faction_id)
        if faction and 'color' in faction:
            color = faction['color']
    
    if not color:
        color = 0x2B2D31
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get('name', ''),
                value=field.get('value', ''),
                inline=field.get('inline', False)
            )
    
    if footer:
        embed.set_footer(text=footer)
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    return embed


async def create_embed_async(
    title: str,
    description: str = None,
    color: int = None,
    faction_id: int = None,
    fields: list = None,
    footer: str = None,
    thumbnail: str = None,
    image: str = None,
    user_id: int = None
) -> discord.Embed:
    if faction_id and not color:
        faction = cache.get_faction(faction_id)
        if faction and 'color' in faction:
            color = faction['color']
    
    if not color:
        color = 0x2B2D31
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get('name', ''),
                value=field.get('value', ''),
                inline=field.get('inline', False)
            )
    
    custom_message_text = None
    if user_id:
        try:
            query = "SELECT message FROM custom_user_messages WHERE user_id = $1"
            data = await db.fetchrow(query, user_id)
            if data and data['message']:
                custom_message_text = f"💬 {data['message']}"
        except Exception:
            pass
    
    if custom_message_text and footer:
        embed.set_footer(text=f"{footer} | {custom_message_text}")
    elif custom_message_text:
        embed.set_footer(text=custom_message_text)
    elif footer:
        embed.set_footer(text=footer)
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    return embed

LOG_RULE = "─" * 30
BAR_FILLED = "█"
BAR_EMPTY = "░"
FIELD_LIMIT = 1024
PANEL_W = 30


def rule(width: int = 30) -> str:
    return "─" * width


def banner(title: str, width: int = PANEL_W) -> str:
    return f"**{title.upper()}**"


def route_bar(src: str, dst: str, width: int = PANEL_W, broken: bool = False) -> str:
    arrow = "to (intercepted)" if broken else "to"
    return f"**{src}** {arrow} **{dst}**"


def meta_line(left: str, right: str = "", width: int = PANEL_W) -> str:
    if right:
        return f"{left} {right}"
    return left


def panel(lines: list) -> str:
    cleaned = []
    for line in lines:
        text = " ".join(str(line).split())
        if not text or not text.strip("=-_─ "):
            continue
        cleaned.append(text)
    return "\n".join(cleaned)


def terminal_panel(title: str, meta: list = None, body: list = None, width: int = PANEL_W) -> str:
    parts = [f"**{title.upper()}**"] if title else []
    for line in (meta or []):
        text = " ".join(str(line).split())
        if text:
            parts.append(text)
    for line in (body or []):
        text = " ".join(str(line).split())
        if text:
            parts.append(text)
    return "\n".join(parts)


def progress_bar(current: float, target: float, width: int = 10) -> str:
    if target <= 0:
        filled = 0
    else:
        filled = int(min(max(current / target, 0), 1) * width)
    return BAR_FILLED * filled + BAR_EMPTY * (width - filled)


def stamp(dt: datetime = None, style: str = "f") -> str:
    dt = dt or datetime.now(timezone.utc)
    return f"<t:{int(dt.timestamp())}:{style}>"


def manifest_block(rows: list, headers: list = None, align: list = None) -> str:
    rows = [[str(c) if c is not None else "" for c in row] for row in rows]
    if not rows:
        return ""

    lines = []
    for row in rows:
        cells = [c for c in row if c != ""]
        if not cells:
            continue
        if len(cells) == 1:
            lines.append(cells[0])
        else:
            lines.append(f"**{cells[0]}** " + " · ".join(cells[1:]))

    text = "\n".join(lines)
    if len(text) <= FIELD_LIMIT:
        return text

    trimmed = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > FIELD_LIMIT - 16:
            trimmed.append("... truncated")
            break
        trimmed.append(line)
        size += len(line) + 1
    return "\n".join(trimmed)


def kv_field(name: str, pairs, inline: bool = True) -> dict:
    if isinstance(pairs, dict):
        pairs = list(pairs.items())
    value = "\n".join(f"**{k}** {v}" for k, v in pairs)
    return {"name": name, "value": value, "inline": inline}


def log_embed(
    title: str,
    subtitle: str = None,
    color: int = None,
    faction_id: int = None,
    fields: list = None,
    footer: str = None,
    description: str = None,
) -> discord.Embed:
    parts = []
    if subtitle:
        parts.append(subtitle)
        parts.append(LOG_RULE)
    if description:
        parts.append(description)
    return create_embed(
        title=title.upper() if title else title,
        description="\n".join(parts) if parts else None,
        color=color,
        faction_id=faction_id,
        fields=fields,
        footer=footer,
    )


def error_embed(title: str = "Error", message: str = None, description: str = None) -> discord.Embed:
    text = description if description is not None else message
    if text is None:
        text = title
        title = "Error"
    
    return discord.Embed(
        title=title,
        description=text,
        color=0xFF0000,
        timestamp=datetime.now(timezone.utc)
    )

def success_embed(title: str = "Success", message: str = None, description: str = None) -> discord.Embed:
    text = description if description is not None else message
    if text is None:
        text = title
        title = "Success"
    
    return discord.Embed(
        title=title,
        description=text,
        color=0x00FF00,
        timestamp=datetime.now(timezone.utc)
    )


async def add_custom_message(embed: discord.Embed, user_id: int) -> discord.Embed:
    try:
        query = "SELECT message FROM custom_user_messages WHERE user_id = $1"
        data = await db.fetchrow(query, user_id)

        if data and data['message']:
            current_footer = embed.footer.text if embed.footer else ""
            if current_footer:
                new_footer = f"{current_footer} | {data['message']}"
            else:
                new_footer = f"{data['message']}"
            embed.set_footer(text=new_footer)
    except Exception:
        pass

    return embed


async def _inject_custom_message(embed: discord.Embed, user_id: int):
    try:
        data = await db.fetchrow("SELECT message FROM custom_user_messages WHERE user_id = $1", user_id)
        if data and data['message']:
            current = embed.footer.text if embed.footer else ""
            embed.set_footer(text=f"{current} | 💬 {data['message']}" if current else f"💬 {data['message']}")
    except Exception:
        pass


async def send_response(
    interaction: discord.Interaction,
    embed: Optional[discord.Embed] = None,
    content: Optional[str] = None,
    ephemeral: bool = False,
    view: Optional[discord.ui.View] = None,
    add_custom_message: bool = True
):
    if add_custom_message and embed:
        await _inject_custom_message(embed, interaction.user.id)
    kwargs = {"ephemeral": ephemeral}
    if embed:
        kwargs["embed"] = embed
    if content:
        kwargs["content"] = content
    if view:
        kwargs["view"] = view
    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)


async def edit_response(
    interaction: discord.Interaction,
    embed: Optional[discord.Embed] = None,
    content: Optional[str] = None,
    view: Optional[discord.ui.View] = None,
    add_custom_message: bool = True
):
    if add_custom_message and embed:
        await _inject_custom_message(embed, interaction.user.id)
    kwargs = {}
    if embed:
        kwargs["embed"] = embed
    if content:
        kwargs["content"] = content
    if view:
        kwargs["view"] = view
    await interaction.edit_original_response(**kwargs)
