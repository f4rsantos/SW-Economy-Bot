# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import os
import discord
from discord import app_commands
from utils.checks import require_access_level

_ALLOWED_IDS = {int(i) for i in os.getenv("ECHO_ALLOWED_IDS", "").split(",") if i.strip()}


@app_commands.command(name="echo", description="Echo a message")
@app_commands.describe(message="Message to echo")
@require_access_level(0)
async def echo_command(interaction: discord.Interaction, message: str):
    if interaction.user.id not in _ALLOWED_IDS:
        await interaction.response.send_message("I am the supreme ruler of thy economy, you do not get to boss me, I boss you.")
        return

    await interaction.response.defer()
    await interaction.channel.send(message)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass


async def setup(bot):
    bot.tree.add_command(echo_command)
