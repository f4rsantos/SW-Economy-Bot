import discord
from discord import app_commands
from utils.embeds import success_embed, error_embed
from services.scripting.parser import parse
from services.scripting.type_checker import check as type_check
from services.scripting.errors import FALSyntaxError
from services.scripting.script_service import get_script_by_name, update_script
from utils.scripting_helpers import resolve_faction_with_access, trigger_day_from_ast, trigger_type_from_ast


class ScriptEditModal(discord.ui.Modal, title="Edit Faction Script"):
    script_text = discord.ui.TextInput(
        label="Script",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )

    def __init__(self, faction_name: str, script_name: str):
        super().__init__()
        self.faction_name = faction_name
        self.script_name = script_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        faction_data, err = await resolve_faction_with_access(interaction, self.faction_name)
        if err:
            await interaction.followup.send(embed=error_embed(err))
            return

        script = await get_script_by_name(faction_data["id"], self.script_name)
        if not script:
            await interaction.followup.send(
                embed=error_embed(f"No active script named '{self.script_name}'.")
            )
            return

        text = self.script_text.value

        try:
            ast = parse(text)
        except FALSyntaxError as e:
            await interaction.followup.send(embed=error_embed(f"Syntax error: {e}"))
            return

        tc = type_check(ast)
        if not tc.ok:
            msg = "\n".join(tc.errors[:5])
            await interaction.followup.send(embed=error_embed(f"Type error:\n{msg}"))
            return

        trigger_day = trigger_day_from_ast(ast)
        trigger_type = trigger_type_from_ast(ast)

        try:
            await update_script(
                script_id=script["id"],
                faction_id=faction_data["id"],
                script_text=text,
                trigger_day=trigger_day,
                trigger_type=trigger_type,
            )
        except ValueError as e:
            await interaction.followup.send(embed=error_embed(str(e)))
            return

        runs_on = "Manual Trigger" if trigger_type == "manual" else (trigger_day or "Income Day")
        embed = success_embed(
            title="Script Updated",
            description=f"Script **{script['name']}** updated. Runs on: **{runs_on}**",
        )
        await interaction.followup.send(embed=embed)


@app_commands.command(name="edit", description="Edit an existing faction script")
@app_commands.describe(faction="Faction name", name="Script name")
async def script_edit(interaction: discord.Interaction, faction: str, name: str):
    modal = ScriptEditModal(faction_name=faction, script_name=name)
    await interaction.response.send_modal(modal)
