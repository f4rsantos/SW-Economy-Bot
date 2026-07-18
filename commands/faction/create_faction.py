import random
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.views import OwnerOnlyView
from database.db_manager import db
from database.cache_manager import cache_manager
from services.map_service import get_world, get_world_by_id
from services.faction_service import (
    create_faction_in_db,
    check_world_space,
    faction_name_exists,
    user_is_registered,
    get_world_hex_count,
    get_world_available_hexes,
)
from utils.faction_utils import FACTION_TYPE_LABELS, FACTION_TYPE_NATION, FACTION_TYPE_COMPANY, FACTION_TYPE_PIRATE


def _parse_faction_type(value: Optional[str]) -> int:
    v = (value or "").strip().lower()
    if v in ("company", "1"):
        return FACTION_TYPE_COMPANY
    if v in ("pirate", "2"):
        return FACTION_TYPE_PIRATE
    return FACTION_TYPE_NATION


def _normalize_color(color: Optional[str]) -> str:
    if not color or color.lower() == "skip":
        return f"#{random.randint(0, 0xFFFFFF):06x}"
    if not color.startswith("#"):
        color = f"#{color}"
    return color


async def _assign_roles(guild: discord.Guild, leader: discord.Member, faction, color: str) -> list[str]:
    results = []
    leader_role = discord.utils.get(guild.roles, name="Leader")
    if leader_role:
        try:
            await leader.add_roles(leader_role, reason="New Faction Leader")
            results.append(f"assigned {leader_role.mention}")
        except discord.Forbidden:
            results.append("failed to assign Leader role (missing permissions)")
        except Exception as e:
            results.append(f"failed to assign Leader role ({e})")
    else:
        results.append("Leader role not found")

    try:
        role_name = faction['formal_name'] if len(faction['formal_name']) < 20 else faction['name']
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if not existing_role:
            faction_role = await guild.create_role(
                name=role_name,
                color=discord.Color(int(color.replace('#', ''), 16)),
                reason="New Faction Created",
                hoist=False
            )
        else:
            faction_role = existing_role
        await leader.add_roles(faction_role, reason="Faction Leader")
        results.append(f"created and assigned {faction_role.mention}")
    except discord.Forbidden:
        results.append("failed to create/assign faction role (missing permissions)")
    except Exception as e:
        results.append(f"failed to create/assign faction role ({e})")

    return results


def _build_success_embed(faction, leader_name: str, leader: discord.Member, color: str, faction_type: int, flag: str, starting_world_id) -> discord.Embed:
    embed = success_embed(title="Faction Created", description=f"**{faction['formal_name']}** has been established!")
    embed.color = int(color.replace('#', ''), 16)
    embed.add_field(name="Name", value=faction['name'], inline=True)
    embed.add_field(name="Leader", value=f"{leader_name} ({leader.mention})", inline=True)
    embed.add_field(name="Color", value=color, inline=True)
    embed.add_field(name="Flag", value=flag if flag else "None", inline=True)
    embed.add_field(name="Type", value=FACTION_TYPE_LABELS.get(faction_type, "Nation"), inline=True)
    if starting_world_id and faction_type == FACTION_TYPE_NATION:
        embed.add_field(name="Starting Territory", value="50 hexes", inline=True)
    return embed


class FactionSetupModal(discord.ui.Modal, title="Faction Setup - Basic Info"):
    name_input = discord.ui.TextInput(label="Faction Name", placeholder="Enter faction name", required=True, max_length=50)
    starting_world_input = discord.ui.TextInput(label="Starting World Name", placeholder="Enter World Name", required=True, max_length=50)
    color_input = discord.ui.TextInput(label="Faction Color", placeholder="Hex color code (e.g., #ff0000)", required=False, max_length=7, default="#ffffff")
    flag_input = discord.ui.TextInput(label="Flag URL/Emoji", placeholder="Flag emoji or image URL", required=False, max_length=200)
    faction_type_input = discord.ui.TextInput(label="Faction Type", placeholder="nation, company, or pirate", required=False, max_length=10, default="nation")

    def __init__(self, leader_user: discord.Member):
        super().__init__()
        self.leader_user = leader_user

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip().lower()
        world_input = self.starting_world_input.value.strip()

        world_row = await get_world(world_input)
        if not world_row and world_input.isdigit():
            world_row = await get_world_by_id(int(world_input))
        if not world_row:
            await interaction.response.send_message(embed=error_embed("Invalid World", f"Could not find world '{world_input}'."))
            return

        if not name.replace(" ", "").isalpha() or not name.isascii():
            await interaction.response.send_message(embed=error_embed("Invalid Name", "Faction name must contain only English letters (a-z). No numbers or special characters."))
            return

        color = _normalize_color(self.color_input.value.strip())
        if len(color) != 7:
            await interaction.response.send_message(embed=error_embed("Invalid Color", "Color must be in format #RRGGBB"))
            return

        flag = self.flag_input.value.strip() if self.flag_input.value.strip().lower() != "skip" else ""
        faction_type = _parse_faction_type(self.faction_type_input.value)
        starting_world_id = world_row['id']
        leader_name = self.leader_user.display_name

        try:
            async with db.get_connection() as conn:
                async with conn.transaction():
                    if not await check_world_space(conn, starting_world_id):
                        await interaction.response.send_message(embed=error_embed("Error", "Not enough space on world. Need 50 hexes."))
                        return
                    if await faction_name_exists(conn, name):
                        await interaction.response.send_message(embed=error_embed("Name Taken", f"A faction with the name '{name}' already exists."))
                        return
                    if not await user_is_registered(conn, self.leader_user.id):
                        await interaction.response.send_message(embed=error_embed("Leader Not Registered", f"{self.leader_user.mention} is not registered."))
                        return
                    faction = await create_faction_in_db(conn, name, name, color, leader_name, flag, self.leader_user.id, faction_type, starting_world_id)

            cache_manager.cache.setdefault('factions', {})[faction['id']] = dict(faction)
            embed = _build_success_embed(faction, leader_name, self.leader_user, color, faction_type, flag, starting_world_id)
            if interaction.guild:
                roles = await _assign_roles(interaction.guild, self.leader_user, faction, color)
                if roles:
                    embed.add_field(name="Roles", value=", ".join(roles), inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(embed=error_embed("Error", f"Failed to create faction: {e}"))


class SetupMethodView(OwnerOnlyView):
    def __init__(self, owner_id: int, leader_user: discord.Member):
        super().__init__(owner_id=owner_id, timeout=180)
        self.leader_user = leader_user

    @discord.ui.button(label="Interactive Setup", style=discord.ButtonStyle.primary)
    async def interactive_setup(self, interaction: discord.Interaction, _: discord.ui.Button):
        modal = FactionSetupModal(self.leader_user)
        await interaction.response.send_modal(modal)
        self.stop()


@app_commands.command(name="create", description="Create a new faction (Admin)")
@app_commands.describe(
    leader="The leader of the faction",
    name="Faction short name (for quick setup)",
    formal_name="Faction formal name (for quick setup)",
    leader_name="Leader's display name (for quick setup)",
    color="Hex color code (for quick setup)",
    flag="Flag emoji or URL (for quick setup)",
    faction_type="Faction type: nation, company, or pirate (for quick setup)",
    starting_world="Starting world ID or name for territory (optional)"
)
@require_access_level(4)
async def create_faction(
    interaction: discord.Interaction,
    leader: discord.Member,
    name: Optional[str] = None,
    formal_name: Optional[str] = None,
    leader_name: Optional[str] = None,
    color: Optional[str] = None,
    flag: Optional[str] = None,
    faction_type: Optional[str] = "nation",
    starting_world: Optional[str] = None
):
    ftype = _parse_faction_type(faction_type)
    if name is None:
        starting_world_id = None
        if starting_world:
            try:
                starting_world_id = int(starting_world)
            except ValueError:
                world_data = await get_world(starting_world)
                if world_data:
                    starting_world_id = world_data['id']
                else:
                    await interaction.response.send_message(embed=error_embed("Error", f"World '{starting_world}' not found."))
                    return
        view = SetupMethodView(interaction.user.id, leader)
        embed = discord.Embed(
            title="Faction Creation",
            description=f"Creating faction for {leader.mention}\n\nClick **Interactive Setup** to begin.",
            color=0x3498db
        )
        if starting_world_id:
            embed.add_field(name="Starting World", value=f"ID: {starting_world_id}", inline=True)
        await interaction.response.send_message(embed=embed, view=view)
        return

    await interaction.response.defer()

    name = name.lower()
    if not name.replace(" ", "").isalpha() or not name.isascii():
        await interaction.followup.send(embed=error_embed("Invalid Name", "Faction name must contain only English letters (a-z). No numbers or special characters."))
        return

    starting_world_id = None
    if starting_world:
        try:
            starting_world_id = int(starting_world)
        except ValueError:
            world_data = await get_world(starting_world)
            if world_data:
                starting_world_id = world_data['id']
            else:
                await interaction.followup.send(embed=error_embed("Error", f"World '{starting_world}' not found."))
                return

    if not formal_name:
        formal_name = name
    if not leader_name:
        leader_name = leader.display_name
    if not flag:
        flag = ""

    color = _normalize_color(color)
    if len(color) != 7:
        await interaction.followup.send(embed=error_embed("Invalid Color", "Color must be in format #RRGGBB"))
        return

    try:
        async with db.get_connection() as conn:
            async with conn.transaction():
                if starting_world_id:
                    hex_count = await get_world_hex_count(conn, starting_world_id)
                    if hex_count is None:
                        await interaction.followup.send(embed=error_embed("Error", "Starting world not found."))
                        return
                    if not await check_world_space(conn, starting_world_id):
                        available_hexes = await get_world_available_hexes(conn, starting_world_id, hex_count)
                        await interaction.followup.send(embed=error_embed("Error", f"Not enough space on world. Need 50 hexes, have {available_hexes}."))
                        return
                if await faction_name_exists(conn, name):
                    await interaction.followup.send(embed=error_embed("Name Taken", f"A faction with the name '{name}' already exists."))
                    return
                if not await user_is_registered(conn, leader.id):
                    await interaction.followup.send(embed=error_embed("Leader Not Registered", f"{leader.mention} is not registered in the bot."))
                    return
                faction = await create_faction_in_db(conn, name, formal_name, color, leader_name, flag, leader.id, ftype, starting_world_id)

        cache_manager.cache.setdefault('factions', {})[faction['id']] = dict(faction)
        embed = _build_success_embed(faction, leader_name, leader, color, ftype, flag, starting_world_id)
        if interaction.guild:
            roles = await _assign_roles(interaction.guild, leader, faction, color)
            if roles:
                embed.add_field(name="Roles", value=", ".join(roles), inline=False)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Failed to create faction: {e}"))


async def setup(bot):
    pass
