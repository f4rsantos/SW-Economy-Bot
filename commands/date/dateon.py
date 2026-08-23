# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from datetime import datetime
from utils.checks import require_access_level
from utils.date_utils import pretty_date


@app_commands.command(name="dateon", description="Calculate Solar Economy date for a specific time")
@app_commands.describe(year="Date's year", month="Date's month (1-12)", day="Date's day", hour="Date's hour (0-23)")
@require_access_level(0)
async def dateon_command(
    interaction: discord.Interaction,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    hour: Optional[int] = None
):
    now = datetime.now()
    y = year if year is not None else now.year
    mo = month if month is not None else now.month
    d = day if day is not None else now.day
    first_hour = hour if hour is not None else 0
    final_hour = hour if hour is not None else 23

    try:
        first_day = pretty_date(datetime(y, mo, d, first_hour, 0, 0))
        final_day = pretty_date(datetime(y, mo, d, final_hour, 59, 59, 999999))
        hour_text = f"{first_hour}:00-{final_hour}:59"
        day_text = first_day if first_day == final_day else f"a span from {first_day} to {final_day}"
        await interaction.response.send_message(f"The time on {y}/{mo}/{d} {hour_text} is {day_text}")
    except ValueError as e:
        await interaction.response.send_message(f"Invalid date: {e}")


async def setup(bot):
    bot.tree.add_command(dateon_command)
