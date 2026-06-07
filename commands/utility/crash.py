import discord
from discord import app_commands
from database.db_manager import db
from services.utility_service import get_operator_for_player, get_user_access_row
import sys


@app_commands.command(name="crash", description="Emergency bot shutdown")
async def crash_command(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = interaction.user.id

    operator = await get_operator_for_player(user_id)
    user = await get_user_access_row(user_id)
    access_level = user['access_level'] if user else 0

    if access_level < 9 and not operator:
        await interaction.followup.send("You do not have permission to use this command.")
        return

    await interaction.followup.send("Shutting down bot...")
    await db.disconnect()
    sys.exit(0)


async def setup(bot):
    bot.tree.add_command(crash_command)
