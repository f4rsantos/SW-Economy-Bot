import discord
from discord import app_commands


def setup_error_handler(bot):
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        from utils.checks import InsufficientAccessLevel, TOSNotAccepted
        from utils.tos import send_tos_prompt
        from services.dashboard import record_command_error

        cmd_name = interaction.command.name if interaction.command else 'unknown'
        user_tag = str(interaction.user)

        if isinstance(error, TOSNotAccepted):
            await send_tos_prompt(interaction)
            record_command_error(cmd_name, user_tag, 'TOSNotAccepted')
            return
        elif isinstance(error, InsufficientAccessLevel):
            if error.current == -1:
                await interaction.response.send_message(
                    "You declined the Terms of Service. You cannot use this bot.\n"
                    "To accept the ToS and use the bot, please use any command again.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Access denied. This command requires access level {error.required}. "
                    f"You have access level {error.current}.",
                    ephemeral=True
                )
            record_command_error(cmd_name, user_tag, str(error))
            return

        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
            print(f"Command error in '{cmd_name}': {type(original).__name__}: {original}")
            import traceback
            traceback.print_exception(type(original), original, original.__traceback__)
            record_command_error(cmd_name, user_tag, f"{type(original).__name__}: {original}")
        else:
            print(f"Command error: {type(error).__name__}: {error}")
            import traceback
            traceback.print_exception(type(error), error, error.__traceback__)
            record_command_error(cmd_name, user_tag, f"{type(error).__name__}: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while processing the command.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)
        except discord.HTTPException:
            pass
