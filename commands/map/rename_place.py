import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.map_service import rename_world
from services.validation_service import require_world


@app_commands.command(name="rename-place", description="Rename a world (Admin)")
@app_commands.describe(world="Current world name", new_name="New world name")
@require_access_level(7)
async def rename_place(interaction: discord.Interaction, world: str, new_name: str):
    await interaction.response.defer()

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    try:
        await rename_world(world_data['id'], new_name)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="World Renamed", description=f"**{world_data['name']}** → **{new_name}**")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(rename_place)
