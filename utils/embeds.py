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

def error_embed(message: str = None, title: str = "Error", description: str = None) -> discord.Embed:
    text = description if description is not None else message
    if text is None:
        text = "An error occurred"
    
    return discord.Embed(
        title=title,
        description=text,
        color=0xFF0000,
        timestamp=datetime.now(timezone.utc)
    )

def success_embed(message: str = None, title: str = "Success", description: str = None) -> discord.Embed:
    text = description if description is not None else message
    if text is None:
        text = "Operation completed successfully"
    
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
