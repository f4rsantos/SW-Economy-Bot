# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from typing import Optional

TOS_PROMPT = """
Please read the Terms of Service for use of this bot, as displayed in the appropriate channel.

If you accept the Terms of Service, please click Accept below. You must be 13 or older to use this bot.
"""





async def send_tos_prompt(interaction: discord.Interaction) -> discord.Message:
    embed = discord.Embed(
        title="Welcome to Solar Economy",
        description=TOS_PROMPT,
        color=0x3498db,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Please read and accept to continue")
    view = TOSView()
    try:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return await interaction.original_response()
    except discord.HTTPException:
        simple_message = (
            "**Welcome to Solar Economy**\n\n"
            "To use this bot, you must accept our Terms of Service.\n"
            "By clicking Accept, you agree to our terms and confirm you are 13+ years old.\n\n"
            "Click the buttons below to accept or decline."
        )
        await interaction.response.send_message(simple_message, view=view, ephemeral=True)
        return await interaction.original_response()


class TOSView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.value: Optional[bool] = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from services.user_service import create_user
        try:
            await create_user(interaction.user.id, access_level=0)
        except Exception:
            pass
        self.value = True
        await interaction.response.edit_message(
            content="**Terms accepted!** You can now use Solar Economy commands.",
            embed=None, view=None
        )
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from services.user_service import create_user
        try:
            await create_user(interaction.user.id, access_level=-1)
        except Exception:
            pass
        self.value = False
        await interaction.response.edit_message(
            content="**Terms declined.** You cannot use Solar Economy commands. You can accept later by using any command.",
            embed=None, view=None
        )
        self.stop()
