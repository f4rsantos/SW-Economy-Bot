# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level


@app_commands.command(name="ping", description="Ping the bot")
@require_access_level(0)
async def ping_command(interaction: discord.Interaction):
    latency_ms = round(interaction.client.latency * 1000)
    await interaction.response.send_message(f'Pong! ({latency_ms}ms)')


async def setup(bot):
    bot.tree.add_command(ping_command)
