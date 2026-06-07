import asyncio
import discord
from discord import app_commands
import os
import math
from datetime import datetime, timezone
from utils.embeds import error_embed
from services.user_service import get_user_access_level
from services.utility_service import (
    get_continuity_triggered_at,
    get_active_operator_count,
    set_continuity_triggered_at,
    reset_continuity_state,
)

FER0_ID = int(os.getenv("FER0_ID", "0"))
DESIGNATED_SUCCESSOR_ID = int(os.getenv("DESIGNATED_SUCCESSOR_ID", "0"))


def _parse_date(date_str: str) -> datetime | None:
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


async def _verify_license_key(supabase_client, key: str) -> bool:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase_client.rpc("verify_license", {"p_input_key": key}).execute(),
    )
    return bool(result.data)


async def _scan_for_fer0_messages(client: discord.Client, after: datetime) -> str | None:
    for guild in client.guilds:
        for channel in guild.text_channels:
            perms = channel.permissions_for(guild.me)
            if not (perms.read_messages and perms.read_message_history):
                continue
            try:
                async for message in channel.history(after=after, limit=200, oldest_first=True):
                    if message.author.id == FER0_ID:
                        return message.jump_url
            except (discord.Forbidden, discord.HTTPException):
                continue
    return None


class ContinuityGroup(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="continuity",
            description="Project Continuity Protocol (ToS §2.10)",
        )

    @app_commands.command(
        name="activate",
        description="Initiate the Project Continuity Protocol (Designated Successor only)",
    )
    @app_commands.describe(
        last_known_time="Date of Fer0's last known appearance (e.g. 2026-01-01)",
        license_keys="Comma-separated operator license keys",
    )
    async def activate(self, interaction: discord.Interaction, last_known_time: str, license_keys: str):
        if interaction.user.id != DESIGNATED_SUCCESSOR_ID:
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "Only the Designated Successor may initiate the Continuity Protocol."),
                ephemeral=True,
            )
            return

        triggered_at = await get_continuity_triggered_at()
        if triggered_at:
            await interaction.response.send_message(
                embed=error_embed("Already Active", "The Continuity Protocol is already active."),
                ephemeral=True,
            )
            return

        last_seen = _parse_date(last_known_time)
        if not last_seen:
            await interaction.response.send_message(
                embed=error_embed("Invalid Date", "Could not parse the supplied date. Use a format like `2026-01-01` or `January 1, 2026`."),
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc)
        absence_days = (now - last_seen).days
        if absence_days < 15:
            await interaction.response.send_message(
                embed=error_embed(
                    "Date Verification Failed",
                    f"The submitted last known appearance date does not meet the minimum "
                    f"**15-day** absence requirement "
                    f"(submitted date implies only **{absence_days}** day(s)).",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        found_msg_link = await _scan_for_fer0_messages(interaction.client, last_seen)
        if found_msg_link:
            await interaction.followup.send(
                embed=error_embed(
                    "Date Verification Failed",
                    f"A message from Fer0 was found **after** the submitted date "
                    f"(`{last_seen.strftime('%Y-%m-%d')}`).\n\n"
                    f"**Message:** {found_msg_link}\n\n"
                    f"The submitted last known appearance date is incorrect.",
                ),
                ephemeral=True,
            )
            return

        submitted_keys = [k.strip() for k in license_keys.split(",") if k.strip()]
        total_operators = await get_active_operator_count()

        if not total_operators:
            await interaction.followup.send(
                embed=error_embed("No Operators", "No active operators are registered."),
                ephemeral=True,
            )
            return

        supabase_client = getattr(interaction.client, "supabase_client", None)
        if not supabase_client:
            await interaction.followup.send(
                embed=error_embed("Internal Error", "Supabase client unavailable."),
                ephemeral=True,
            )
            return

        valid_count = 0
        seen_valid: set[str] = set()
        for key in submitted_keys:
            if key in seen_valid:
                continue
            if await _verify_license_key(supabase_client, key):
                seen_valid.add(key)
                valid_count += 1

        required = total_operators if total_operators < 3 else max(3, math.ceil(total_operators / 2))
        if valid_count < required:
            await interaction.followup.send(
                embed=error_embed(
                    "Insufficient Keys",
                    f"Quorum requires **{required}** valid operator key(s). "
                    f"**{valid_count}** distinct valid key(s) were submitted.",
                ),
                ephemeral=True,
            )
            return

        await set_continuity_triggered_at(now)

        try:
            fer0 = await interaction.client.fetch_user(FER0_ID)
            await fer0.send(
                f"⚠️ <@{FER0_ID}> **PROJECT CONTINUITY PROTOCOL — ACTIVATED**\n\n"
                f"The Designated Successor has formally initiated the Continuity Protocol.\n"
                f"**Reported last known appearance:** `{last_seen.strftime('%Y-%m-%d')}`\n"
                f"**Triggered at:** <t:{int(now.timestamp())}:F>\n\n"
                f"You have **7 days** to return and run `/continuity deactivate` "
                f"to cancel the Protocol."
            )
        except Exception:
            pass

        embed = discord.Embed(
            title="⚠️ Project Continuity Protocol — ACTIVATED",
            description=(
                f"The Designated Successor has formally initiated the "
                f"Project Continuity Protocol per **ToS §2.10**.\n\n"
                f"**Reported last known appearance:** `{last_seen.strftime('%Y-%m-%d')}`\n"
                f"**Triggered:** <t:{int(now.timestamp())}:F>\n\n"
                f"If any doubt rests on **anyone**'s mind of the disappearance or the need to activate the protocol, use /continuity deactivate."
            ),
            color=discord.Color.red(),
        )
        await interaction.channel.send(content=f"<@{FER0_ID}>", embed=embed)

    @app_commands.command(name="deactivate", description="Deactivate the Project Continuity Protocol")
    async def deactivate(self, interaction: discord.Interaction):
        user_level = await get_user_access_level(interaction.user.id)
        if user_level < 0:
            await interaction.response.send_message(
                embed=error_embed("Access Denied", "Only users holding a role may deactivate the Continuity Protocol."),
                ephemeral=True,
            )
            return

        triggered_at = await get_continuity_triggered_at()
        if not triggered_at:
            await interaction.response.send_message(
                embed=error_embed("Not Active", "The Continuity Protocol is not currently active."),
                ephemeral=True,
            )
            return

        await reset_continuity_state()

        now = datetime.now(timezone.utc)
        await interaction.response.defer()

        try:
            fer0 = await interaction.client.fetch_user(FER0_ID)
            await fer0.send(
                f"<@{FER0_ID}> **PROJECT CONTINUITY PROTOCOL — DEACTIVATED**\n\n"
                f"The Protocol has been deactivated by **{interaction.user}** "
                f"(`{interaction.user.id}`).\n"
                f"**Originally triggered:** <t:{int(triggered_at.timestamp())}:F>\n"
                f"**Deactivated at:** <t:{int(now.timestamp())}:F>"
            )
        except Exception:
            pass

        embed = discord.Embed(
            title="Project Continuity Protocol — DEACTIVATED",
            description=(
                f"The Continuity Protocol has been deactivated by "
                f"**{interaction.user.display_name}**.\n\n"
                f"**Originally triggered:** <t:{int(triggered_at.timestamp())}:F>\n"
                f"**Deactivated:** <t:{int(now.timestamp())}:F>"
            ),
            color=discord.Color.green(),
        )
        await interaction.channel.send(content=f"<@{FER0_ID}>", embed=embed)


async def setup(bot):
    bot.tree.add_command(ContinuityGroup())
