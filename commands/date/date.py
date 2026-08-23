# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.date_utils import pretty_date


@app_commands.command(name="date", description="Display current Solar Economy game date")
@require_access_level(0)
async def date_command(interaction: discord.Interaction):
    await interaction.response.send_message(pretty_date())


async def setup(bot):
    bot.tree.add_command(date_command)
