import discord
from discord import app_commands
import random
import re
from utils.embeds import error_embed


@app_commands.command(name="roll", description="Roll dice")
@app_commands.describe(dice="Dice to roll (e.g., 2d6, 1d20, 3d10)")
async def roll(interaction: discord.Interaction, dice: str):
    match = re.match(r'^(\d+)d(\d+)$', dice.lower())
    if not match:
        await interaction.response.send_message(embed=error_embed("Invalid Format", "Use format: XdX (e.g., 2d6, 1d20, 3d10)"), ephemeral=True)
        return

    num_dice = int(match.group(1))
    die_size = int(match.group(2))

    if not (1 <= num_dice <= 100):
        await interaction.response.send_message(embed=error_embed("Invalid", "Number of dice must be between 1 and 100."), ephemeral=True)
        return

    if not (2 <= die_size <= 1000):
        await interaction.response.send_message(embed=error_embed("Invalid", "Die size must be between 2 and 1000."), ephemeral=True)
        return

    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls)

    embed = discord.Embed(title=f"Dice Roll: {dice}", color=0x00ff00)
    if num_dice <= 20:
        embed.add_field(name="Rolls", value=", ".join(str(r) for r in rolls), inline=False)
    embed.add_field(name="Total", value=f"**{total}**", inline=False)
    if num_dice > 1:
        embed.add_field(name="Average", value=f"{total / num_dice:.2f}", inline=True)
        embed.add_field(name="Highest", value=str(max(rolls)), inline=True)
        embed.add_field(name="Lowest", value=str(min(rolls)), inline=True)

    await interaction.response.send_message(embed=embed)


async def setup(bot):
    bot.tree.add_command(roll)
