# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level


@app_commands.command(name="list", description="Show vehicle rating formulas and cost guide")
@require_access_level(0)
async def list_rates(interaction: discord.Interaction):
    await interaction.response.defer()

    embed = discord.Embed(title="Spacecraft Rating Guide", description="Cost formulas for vehicle designs", color=0x3498db)
    embed.add_field(
        name="Command Usage",
        value="To rate a spaceship, use /rate ship\n"
              "To rate a sea vessel, use /rate ship with the sea toggle\n"
              "To rate a ground vehicle, use /rate ground\n"
              "To rate an aircraft, use /rate air\n"
              "To rate a missile, use /rate missile\n"
              "To rate infantry, use /rate infantry\n\n"
              "For the first 4, you can write your faction, and a name (and optionally a designation), to register the vehicle.",
        inline=False
    )
    embed.set_footer(text="All calculations are done automatically.")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(list_rates)
