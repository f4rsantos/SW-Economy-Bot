# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed


@app_commands.command(name="reload", description="Reload all command modules (Admin Only)")
@require_access_level(9)
async def reload_commands(interaction: discord.Interaction):
    await interaction.response.defer()

    bot = interaction.client
    reloaded = []
    failed = []

    for extension in list(bot.extensions.keys()):
        try:
            await bot.reload_extension(extension)
            reloaded.append(extension)
        except Exception as e:
            failed.append((extension, str(e)))

    if failed:
        embed = error_embed("Reload Completed with Errors", f"Reloaded {len(reloaded)} modules, {len(failed)} failed")
        if reloaded:
            lines = "\n".join(f"• {ext}" for ext in reloaded[:10])
            if len(reloaded) > 10:
                lines += f"\n... and {len(reloaded) - 10} more"
            embed.add_field(name=f"Reloaded ({len(reloaded)})", value=lines, inline=False)
        failed_lines = "\n".join(f"• {ext}: {err[:50]}" for ext, err in failed[:5])
        if len(failed) > 5:
            failed_lines += f"\n... and {len(failed) - 5} more"
        embed.add_field(name=f"Failed ({len(failed)})", value=failed_lines, inline=False)
    else:
        embed = success_embed("Commands Reloaded", f"Successfully reloaded {len(reloaded)} command modules")
        lines = "\n".join(f"• {ext}" for ext in reloaded) if len(reloaded) <= 15 else f"{len(reloaded)} modules reloaded (too many to list)"
        embed.add_field(name="Reloaded Modules", value=lines, inline=False)

    try:
        synced = await bot.tree.sync()
        embed.add_field(name="Command Sync", value=f"Synced {len(synced)} slash commands", inline=False)
    except Exception as e:
        embed.add_field(name="Command Sync", value=f"Failed to sync: {str(e)[:100]}", inline=False)

    embed.set_footer(text=f"Reloaded by {interaction.user.name}")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(reload_commands)
