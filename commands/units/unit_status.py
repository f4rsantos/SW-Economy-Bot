# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from discord.ui import Select
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.views import OwnerOnlyView
from services.fleet_service import set_fleet_status
from services.battle_service import get_battles, enter_battle, next_side_letter, sides_of
from services.validation_service import require_faction, require_unit
from utils.autocomplete import faction_autocomplete

BATTLE_STATUS = "battle"
NEW_BATTLE_VALUE = "new"
NEW_SIDE_VALUE = "new"
BATTLE_OPTION_LIMIT = 24


def build_result_embed(unit_name: str, world_name: str, result: dict, faction_color: int) -> discord.Embed:
    stats_text = "\n".join(
        f"**Side {s.side}:** {s.fleet_count} fleet(s), {int(s.total_cs)} CS" for s in result['stats']
    )
    if result['created']:
        title = "Battle Started"
        body = (
            f"**{unit_name}** has started a battle at **{world_name}**.\n"
            f"**Battle ID:** {result['battle_id']}\n"
            f"**War ID:** {result['war_id']}\n"
            f"**Side:** {result['side']}"
        )
    else:
        title = "Joined Battle"
        body = (
            f"**{unit_name}** has joined Battle #{result['battle_id']} at **{world_name}**.\n"
            f"**Side:** {result['side']}"
        )
    embed = success_embed(title, f"{body}\n\n**Current Battle Status:**\n{stats_text}")
    embed.color = faction_color
    return embed


class SideSelectView(OwnerOnlyView):
    def __init__(self, owner_id: int, unit_data: dict, faction_id: int, faction_color: int,
                 battle_id: int, existing_sides: list):
        super().__init__(owner_id)
        self.unit_data = unit_data
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.battle_id = battle_id
        self.existing_sides = existing_sides

        options = [
            discord.SelectOption(label=f"Side {side}", value=side)
            for side in existing_sides[:BATTLE_OPTION_LIMIT]
        ]
        options.append(discord.SelectOption(
            label=f"New side ({next_side_letter(existing_sides)})",
            value=NEW_SIDE_VALUE,
            description="Fight as a new side in this battle"
        ))
        select = Select(placeholder="Choose a side...", options=options)
        select.callback = self.side_chosen
        self.select = select
        self.add_item(select)

    async def side_chosen(self, interaction: discord.Interaction):
        choice = self.select.values[0]
        side = next_side_letter(self.existing_sides) if choice == NEW_SIDE_VALUE else choice

        try:
            result = await enter_battle(
                self.unit_data['id'], self.faction_id, self.unit_data['position'],
                self.unit_data['world_name'], battle_id=self.battle_id, side=side
            )
        except ValueError as e:
            await interaction.response.edit_message(embed=error_embed("Error", str(e)), view=None)
            return

        unit_name = self.unit_data['name'] or f"Unit #{self.unit_data['faction_fleet_number']}"
        embed = build_result_embed(unit_name, self.unit_data['world_name'], result, self.faction_color)
        await interaction.response.edit_message(embed=embed, view=None)


class BattleSelectView(OwnerOnlyView):
    def __init__(self, owner_id: int, unit_data: dict, faction_id: int, faction_color: int, battles: list):
        super().__init__(owner_id)
        self.unit_data = unit_data
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.battles = {str(b.id): b for b in battles}

        options = []
        for battle in battles[:BATTLE_OPTION_LIMIT]:
            sides = sides_of(battle)
            sides_text = ", ".join(sides) if sides else "no sides yet"
            options.append(discord.SelectOption(
                label=f"Battle #{battle.id}"[:100],
                value=str(battle.id),
                description=f"{battle.fleet_count} unit(s), sides: {sides_text}"[:100]
            ))
        options.append(discord.SelectOption(
            label="New battle",
            value=NEW_BATTLE_VALUE,
            description="Start a separate battle at this world"
        ))
        select = Select(placeholder="Choose a battle to join...", options=options)
        select.callback = self.battle_chosen
        self.select = select
        self.add_item(select)

    async def battle_chosen(self, interaction: discord.Interaction):
        choice = self.select.values[0]

        if choice == NEW_BATTLE_VALUE:
            try:
                result = await enter_battle(
                    self.unit_data['id'], self.faction_id, self.unit_data['position'],
                    self.unit_data['world_name']
                )
            except ValueError as e:
                await interaction.response.edit_message(embed=error_embed("Error", str(e)), view=None)
                return
            unit_name = self.unit_data['name'] or f"Unit #{self.unit_data['faction_fleet_number']}"
            embed = build_result_embed(unit_name, self.unit_data['world_name'], result, self.faction_color)
            await interaction.response.edit_message(embed=embed, view=None)
            return

        battle = self.battles[choice]
        view = SideSelectView(self.owner_id, self.unit_data, self.faction_id,
                              self.faction_color, battle.id, sides_of(battle))
        embed = success_embed(
            "Choose a Side",
            f"Joining Battle #{battle.id} at **{self.unit_data['world_name']}**.\nPick a side to fight on."
        )
        embed.color = self.faction_color
        await interaction.response.edit_message(embed=embed, view=view)


async def handle_battle_status(interaction: discord.Interaction, unit_data: dict,
                               faction_id: int, faction_color: int):
    battles = await get_battles(world_id=unit_data['position'])

    if not battles:
        try:
            result = await enter_battle(
                unit_data['id'], faction_id, unit_data['position'], unit_data['world_name']
            )
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return
        unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
        await interaction.followup.send(
            embed=build_result_embed(unit_name, unit_data['world_name'], result, faction_color)
        )
        return

    view = BattleSelectView(interaction.user.id, unit_data, faction_id, faction_color, battles)
    embed = success_embed(
        "Battles in Progress",
        f"There are {len(battles)} battle(s) at **{unit_data['world_name']}**.\n"
        "Pick one to join, or start a new battle."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed, view=view)


@app_commands.command(name="status", description="Change unit status")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="Unit number (faction-specific) or name",
    status="New status"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Idle",       value="idle"),
    app_commands.Choice(name="defence",    value="defence"),
    app_commands.Choice(name="Patrol",     value="patrol"),
    app_commands.Choice(name="FTL Supply", value="ftl supply"),
    app_commands.Choice(name="Battle",     value=BATTLE_STATUS),
])
@require_access_level(0)
@ephemeral_capable('faction')
async def unit_status_command(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    status: str
):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_unit_data = await require_unit(unit_id, faction_data.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    current_status = unit_data['status_name'].lower()
    if current_status == 'debris':
        await interaction.followup.send(embed=error_embed("Error", "Debris units cannot change status. Repair them first."))
        return

    if status == BATTLE_STATUS:
        if current_status == 'in combat':
            await interaction.followup.send(embed=error_embed("Error", "This unit is already in combat."))
            return
        await handle_battle_status(interaction, unit_data, faction_data.id, faction_color)
        return

    if current_status == 'in combat':
        await interaction.followup.send(embed=error_embed(
            "Error",
            "Units in combat must leave their battle first. Use `/battle leave-battle`."
        ))
        return

    try:
        await set_fleet_status(unit_data['id'], status)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    embed = success_embed(
        "Unit Status Changed",
        f"**{unit_name}**\n\n{unit_data['status_name']} → {status.title()}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    unit_status_command.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_status_command)
