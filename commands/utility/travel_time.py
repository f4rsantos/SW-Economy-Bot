# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.embeds import error_embed
from services.travel_time_service import calculate_travel_time, format_travel_time


@app_commands.command(name="travel-time", description="Calculate travel time between two worlds")
@app_commands.describe(origin="Starting world (e.g. Earth)", destination="Destination world (e.g. Mars)")
async def travel_time(interaction: discord.Interaction, origin: str, destination: str):
    await interaction.response.defer()

    try:
        time_delta = await calculate_travel_time(origin, destination)
        time_str = await format_travel_time(time_delta)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Navigation Error", f"Failed to calculate course: {str(e)}"))
        return

    embed = discord.Embed(
        title="Travel Time Simulation",
        description=f"Calculating trajectory from **{origin}** to **{destination}**...",
        color=discord.Color.blue()
    )
    embed.add_field(name="Estimated Travel Time", value=f"**{time_str}**", inline=False)
    embed.set_footer(text="Based on current orbital alignment.")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(travel_time)
