# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
import io

import httpx

from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.map_service import get_world_factions
from services.validation_service import require_world
from services.map_overlay_service import fetch_world_map_config, render_world_overlay_image


@app_commands.command(name="view", description="View world territory list plus map overlay")
@app_commands.describe(world="World name")
@require_access_level(0)
async def view(interaction: discord.Interaction, world: str):
    await interaction.response.defer()

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    world_id = world_data['id']
    max_hexes = world_data['hex_count']

    factions = await get_world_factions(world_id)
    if not factions:
        await interaction.followup.send(
            embed=error_embed("No Claims", f"No factions have claimed hexes on {world_data['name']}."),
        )
        return

    total_claimed = sum(f.territory for f in factions)
    embed = discord.Embed(
        title=f"Map View - {world_data['name']}",
        description=(
            f"**Total Hexes:** {max_hexes:,}\n"
            f"**Claimed:** {total_claimed:,}\n"
            f"**Available:** {max_hexes - total_claimed:,}"
        ),
        color=hex_to_int(factions[0].color),
    )

    lines = [f"**{f.display_name}:** {f.territory:,} ({f.territory / max_hexes * 100:.1f}%)" for f in factions]
    for i in range(0, len(lines), 20):
        embed.add_field(name="Factions" if i == 0 else "...", value="\n".join(lines[i:i + 20]), inline=False)

    config = await fetch_world_map_config(world_data['name'])
    if not config:
        embed.set_footer(text="No map config found in Firestore for this world. Showing territory list only.")
        await interaction.followup.send(embed=embed)
        return

    background = config.get("background")
    overlay = config.get("overlay")
    if not background or overlay is None:
        embed.set_footer(text="Map config missing background/overlay fields. Showing territory list only.")
        await interaction.followup.send(embed=embed)
        return

    try:
        image_bytes = await render_world_overlay_image(background, overlay, defaults=config.get("_hmg_defaults"), world_name=world_data['name'])
        file = discord.File(fp=io.BytesIO(image_bytes), filename="map_view.png")
        embed.set_image(url="attachment://map_view.png")
        await interaction.followup.send(embed=embed, file=file)
    except httpx.HTTPStatusError as e:
        embed.set_footer(text=f"Overlay render failed: HTTP {e.response.status_code} — {e.request.url}")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        embed.set_footer(text=f"Overlay render failed: {e}")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(view)
