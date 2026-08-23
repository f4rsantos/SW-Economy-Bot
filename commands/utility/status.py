# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from datetime import datetime, timezone
from utils.checks import require_access_level
from services.dashboard import _get_snapshot, get_flags


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


@app_commands.command(name="status", description="Bot status — DB, ping, command stats, active flags")
@require_access_level(0)
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer()

    snap  = _get_snapshot()
    flags = get_flags()

    total = snap['commands_total']
    ok    = snap['commands_success']
    err   = snap['commands_error']
    rate  = round(ok / total * 100, 1) if total else 100.0

    ping_ms = snap['ping_ms']
    if ping_ms < 150:
        ping_str = f"🟢 {ping_ms} ms"
    elif ping_ms < 400:
        ping_str = f"🟡 {ping_ms} ms"
    else:
        ping_str = f"🔴 {ping_ms} ms"

    db_str = "🟢 Connected" if snap['db_connected'] else "🔴 Disconnected"
    if snap['db_size_gb'] is not None:
        db_str += f"  ({snap['db_size_gb']} GB)"

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
    embed = discord.Embed(title=f"Bot Status  •  v{version}", color=0x3498db)
    embed.add_field(name="Database",      value=db_str,   inline=True)
    embed.add_field(name="Ping",          value=ping_str, inline=True)
    embed.add_field(name="Uptime",        value=_uptime(snap.get('started_at')), inline=True)
    embed.add_field(name="Commands",      value=f"{total} total  •  {ok} ok  •  {err} errors", inline=True)
    embed.add_field(name="Success Rate",  value=rate_str, inline=True)
    embed.add_field(name="Cache",         value=f"{snap['cache_factions']} factions  •  {snap['cache_players']} players", inline=True)
    embed.add_field(name="Income",        value=income_str, inline=False)
    embed.add_field(name="Active Flags",  value=flags_str,  inline=False)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(status_command)
