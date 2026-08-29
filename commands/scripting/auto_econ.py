# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional

from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.autocomplete import faction_autocomplete, world_autocomplete
from services.validation_service import require_world
from services.scripting.auto_econ_service import (
    AutoEconError,
    StopCondition,
    FOCUS_OPTIONS,
    MIN_FOCUS_PCT,
    MAX_FOCUS_PCT,
    STOP_KIND_BUILDING_COUNT,
    STOP_KIND_RESOURCE_CAPACITY,
    STOP_KIND_DATE,
    find_existing_auto_econ_script,
    save_auto_econ_script,
)
from utils.scripting_helpers import resolve_faction_with_access

DISCORD_MAX_INT = 9007199254740991

DAY_CHOICES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


def _build_stop_conditions(
    stop_building_count: Optional[int],
    stop_resource: Optional[str],
    stop_resource_amount: Optional[int],
    stop_day: Optional[str],
) -> list[StopCondition]:
    stops: list[StopCondition] = []

    if stop_building_count is not None:
        stops.append(StopCondition(kind=STOP_KIND_BUILDING_COUNT, threshold=stop_building_count))

    if stop_resource is not None or stop_resource_amount is not None:
        if stop_resource is None or stop_resource_amount is None:
            raise AutoEconError("Both stop_resource and stop_resource_amount are required together")
        stops.append(StopCondition(
            kind=STOP_KIND_RESOURCE_CAPACITY,
            resource=stop_resource.upper(),
            threshold=stop_resource_amount,
        ))

    if stop_day is not None:
        stops.append(StopCondition(kind=STOP_KIND_DATE, day=stop_day.upper(), threshold=0))

    return stops


class ConfirmAutoEconOverwriteView(discord.ui.View):
    def __init__(self, faction, faction_name: str, created_by: int, focus: str, focus_pct: int,
                 budget_pct: int, world_name: Optional[str], stop_conditions: list, trigger_day: Optional[str]):
        super().__init__(timeout=60)
        self.faction = faction
        self.faction_name = faction_name
        self.created_by = created_by
        self.focus = focus
        self.focus_pct = focus_pct
        self.budget_pct = budget_pct
        self.world_name = world_name
        self.stop_conditions = stop_conditions
        self.trigger_day = trigger_day

    @discord.ui.button(label="Overwrite Auto Econ Script", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            row = await save_auto_econ_script(
                faction_id=self.faction.id,
                faction_name=self.faction_name,
                created_by=self.created_by,
                focus=self.focus,
                focus_pct=self.focus_pct,
                budget_pct=self.budget_pct,
                world_name=self.world_name,
                stop_conditions=self.stop_conditions,
                trigger_day=self.trigger_day,
            )
        except AutoEconError as e:
            await interaction.response.edit_message(embed=error_embed(str(e)), view=None)
            return

        await interaction.response.edit_message(
            embed=success_embed(
                title="Auto Econ Regenerated",
                description=(
                    f"Auto econ script for **{self.faction.display_name}** was overwritten.\n"
                    f"Any hand edits to the previous version were replaced."
                ),
            ),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=error_embed("Auto econ generation cancelled. Your existing script was not changed."),
            view=None,
        )


@app_commands.command(name="auto-econ", description="Generate a weekly automation script from simple parameters")
@app_commands.describe(
    faction="Faction name",
    focus="Resource or building type to weight development towards",
    focus_pct="Strength of the focus, 40 to 100 percent (ignored for BALANCED)",
    budget_pct="Percent of your CM treasury to spend per run (1-100)",
    world="World to build on (optional, auto picks best world per resource when omitted)",
    stop_building_count="Stop permanently once you reach this many of the primary building",
    stop_resource="Resource to watch for the capacity stop condition (optional)",
    stop_resource_amount="Stop permanently once this resource reaches this amount (optional)",
    stop_day="Stop permanently once this day of the week is reached (optional)",
    trigger_day="Weekday to run on (defaults to income day)",
)
@app_commands.choices(focus=[app_commands.Choice(name=s, value=s) for s in FOCUS_OPTIONS])
@app_commands.choices(stop_day=[app_commands.Choice(name=d, value=d) for d in DAY_CHOICES])
@app_commands.choices(trigger_day=[app_commands.Choice(name=d, value=d) for d in DAY_CHOICES])
@app_commands.autocomplete(faction=faction_autocomplete, world=world_autocomplete)
@require_access_level(0)
async def script_auto_econ(
    interaction: discord.Interaction,
    faction: str,
    focus: str,
    budget_pct: app_commands.Range[int, 1, 100],
    focus_pct: app_commands.Range[int, MIN_FOCUS_PCT, MAX_FOCUS_PCT] = MAX_FOCUS_PCT,
    world: Optional[str] = None,
    stop_building_count: Optional[app_commands.Range[int, 1, 1000000]] = None,
    stop_resource: Optional[str] = None,
    stop_resource_amount: Optional[app_commands.Range[int, 1, DISCORD_MAX_INT]] = None,
    stop_day: Optional[str] = None,
    trigger_day: Optional[str] = None,
):
    await interaction.response.defer()

    faction_data, err = await resolve_faction_with_access(interaction, faction)
    if err:
        await interaction.followup.send(embed=error_embed(err))
        return

    world_name: Optional[str] = None
    if world:
        world_result = await require_world(world)
        if not world_result.ok:
            await interaction.followup.send(embed=error_embed(world_result.error))
            return
        world_name = world_result.data["name"]

    try:
        stop_conditions = _build_stop_conditions(
            stop_building_count, stop_resource, stop_resource_amount, stop_day,
        )
    except AutoEconError as e:
        await interaction.followup.send(embed=error_embed(str(e)))
        return

    if not stop_conditions:
        await interaction.followup.send(embed=error_embed(
            "Set at least one stop condition (building count, resource capacity, or day)."
        ))
        return

    existing = await find_existing_auto_econ_script(faction_data.id, faction_data.name)
    if existing:
        embed = discord.Embed(
            title="Overwrite Existing Auto Econ Script?",
            description=(
                f"**{faction_data.display_name}** already has an auto econ script "
                f"(**{existing.name}**). Regenerating will overwrite it entirely, "
                f"including any hand edits you made to it.\n\nContinue?"
            ),
            color=0xFF6600,
        )
        view = ConfirmAutoEconOverwriteView(
            faction=faction_data,
            faction_name=faction_data.name,
            created_by=interaction.user.id,
            focus=focus,
            focus_pct=focus_pct,
            budget_pct=budget_pct,
            world_name=world_name,
            stop_conditions=stop_conditions,
            trigger_day=trigger_day,
        )
        await interaction.followup.send(embed=embed, view=view)
        return

    try:
        await save_auto_econ_script(
            faction_id=faction_data.id,
            faction_name=faction_data.name,
            created_by=interaction.user.id,
            focus=focus,
            focus_pct=focus_pct,
            budget_pct=budget_pct,
            world_name=world_name,
            stop_conditions=stop_conditions,
            trigger_day=trigger_day,
        )
    except AutoEconError as e:
        await interaction.followup.send(embed=error_embed(str(e)))
        return
    except ValueError as e:
        await interaction.followup.send(embed=error_embed(str(e)))
        return

    runs_on = trigger_day or "Income Day"
    focus_desc = focus.upper() if focus.upper() == "BALANCED" else f"{focus.upper()} at {focus_pct}%"
    embed = success_embed(
        title="Auto Econ Script Created",
        description=(
            f"Generated and saved an automation script for **{faction_data.display_name}**.\n"
            f"Focus: **{focus_desc}**. Budget: **{budget_pct}%** of CM per run. "
            f"Runs on: **{runs_on}**.\n\n"
            f"You can review or hand-edit it with `/script info` and `/script edit`, but "
            f"running `/script auto-econ` again will regenerate and overwrite it."
        ),
    )
    await interaction.followup.send(embed=embed)
