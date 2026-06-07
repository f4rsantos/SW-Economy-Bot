import discord
from discord import app_commands
from utils.checks import require_access_level
from services.game_service import get_high_score

_GAMES = [
    ('memory', 'Memory'),
    ('snake_normal', 'Snake (Normal)'),
    ('snake_hard', 'Snake (Hard)'),
    ('snake_impossible', 'Snake (Impossible)')
]


@app_commands.command(name="highscores", description="View global high scores")
@require_access_level(0)
async def high_scores(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = discord.Embed(title="Global High Scores", description="Best scores across all players", color=0xFFD700)
    for game_type, display_name in _GAMES:
        row = await get_high_score(game_type)
        if row:
            user = interaction.client.get_user(row['user_id'])
            name = user.name if user else f"User {row['user_id']}"
            embed.add_field(name=display_name, value=f"{name}: {row['score']:,}", inline=True)
        else:
            embed.add_field(name=display_name, value="No record yet", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(high_scores)
