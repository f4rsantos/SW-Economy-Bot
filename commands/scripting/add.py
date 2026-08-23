# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.embeds import success_embed, error_embed
from services.scripting.parser import parse
from services.scripting.type_checker import check as type_check
from services.scripting.errors import FALSyntaxError, FALTypeError, FALSecurityError
from services.scripting.script_service import create_script
from utils.scripting_helpers import resolve_faction_with_access, trigger_day_from_ast, trigger_type_from_ast


class ScriptAddModal(discord.ui.Modal, title="Add Faction Script"):
    script_name = discord.ui.TextInput(
        label="Script name",
        placeholder="e.g. weekly_transfers",
        max_length=100,
        required=True,
    )
    script_text = discord.ui.TextInput(
        label="Script",
        style=discord.TextStyle.paragraph,
        placeholder="START ON MONDAY\nIF CM > 500K:\n    TRANSFER 200K CM FROM Sol TO Athena AT Proxima",
        max_length=4000,
        required=True,
    )

    def __init__(self, faction_name: str):
        super().__init__()
        self.faction_name = faction_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        faction_data, err = await resolve_faction_with_access(interaction, self.faction_name)
        if err:
            await interaction.followup.send(embed=error_embed(err))
            return

        name = self.script_name.value.strip()
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
            script = await create_script(
                faction_id=faction_data.id,
                name=name,
                script_text=text,
                trigger_day=trigger_day,
                trigger_type=trigger_type,
                created_by=interaction.user.id,
            )
        except ValueError as e:
            await interaction.followup.send(embed=error_embed(str(e)))
            return

        runs_on = "Manual Trigger" if trigger_type == "manual" else (trigger_day or "Income Day")
        embed = success_embed(
            title="Script Created",
            description=f"Script **{name}** saved for **{faction_data.display_name}**.\nRuns on: **{runs_on}**",
        )
        await interaction.followup.send(embed=embed)


@app_commands.command(name="add", description="Add an automation script for a faction")
@app_commands.describe(faction="Faction name", name="Script name (unique per faction)")
async def script_add(interaction: discord.Interaction, faction: str, name: str):
    modal = ScriptAddModal(faction_name=faction)
    modal.script_name.default = name
    await interaction.response.send_modal(modal)
