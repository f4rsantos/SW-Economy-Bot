import discord
from discord import app_commands
from datetime import datetime, timezone
from database.db_manager import db
from services.utility_service import get_operator_for_player, get_user_access_row
from services.dashboard import _get_snapshot, get_flags
import sys


def _uptime(started_at_iso: str) -> str:
    if not started_at_iso:
        return '—'
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(started_at_iso)
    total = int(delta.total_seconds())
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h:02d}h {m:02d}m"
    return f"{h:02d}h {m:02d}m {s:02d}s"


@app_commands.command(name="crash", description="Emergency bot shutdown")
async def crash_command(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = interaction.user.id

    operator = await get_operator_for_player(user_id)
    user = await get_user_access_row(user_id)
    access_level = user['access_level'] if user else 0

    if access_level < 9 and not operator:
        await interaction.followup.send("You do not have permission to use this command.")
        return

    snap = _get_snapshot()
    flags = get_flags()

    total = snap['commands_total']
    ok    = snap['commands_success']
    err   = snap['commands_error']
    rate  = round(ok / total * 100, 1) if total else 100.0

    if rate >= 95:
        rate_str = f"🟢 {rate}%"
    elif rate >= 80:
        rate_str = f"🟡 {rate}%"
    else:
        rate_str = f"🔴 {rate}%"

    active_flags = [k for k, v in flags.items() if v]
    flags_str = "  ".join(f"`{f}`" for f in active_flags) if active_flags else "*None*"

    income_str = (
        f"Last: <t:{int(datetime.fromisoformat(snap['income_last_run']).timestamp())}:R>  ({snap['income_runs']} run(s))"
        if snap.get('income_last_run') else "*Not run this session*"
    )

    version = snap.get('bot_version') or 'unknown'
    embed = discord.Embed(title=f"Shutting Down...  •  v{version}", color=0xe74c3c)
    embed.add_field(name="Uptime",       value=_uptime(snap.get('started_at')), inline=True)
    embed.add_field(name="Commands",     value=f"{total} total  •  {ok} ok  •  {err} errors", inline=True)
    embed.add_field(name="Success Rate", value=rate_str, inline=True)
    embed.add_field(name="Cache",        value=f"{snap['cache_factions']} factions  •  {snap['cache_players']} players", inline=True)
    embed.add_field(name="Income",       value=income_str, inline=False)
    embed.add_field(name="Active Flags", value=flags_str,  inline=False)

    await interaction.followup.send(embed=embed)
    await db.disconnect()
    sys.exit(0)


async def setup(bot):
    bot.tree.add_command(crash_command)
