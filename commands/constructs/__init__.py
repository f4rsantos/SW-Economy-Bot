# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands

class RateGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="rate", description="Vehicle and construct rating commands")

async def setup(bot):
    from commands.constructs import (
        air_rate, ship_rate, ground_rate, infantry_rate, missile_rate, list_rates
    )

    rate_group = RateGroup()

    rate_group.add_command(air_rate.air_rate)
    rate_group.add_command(ship_rate.ship_rate)
    rate_group.add_command(ground_rate.ground_rate)
    rate_group.add_command(infantry_rate.infantry_rate)
    rate_group.add_command(missile_rate.missile_rate)
    rate_group.add_command(list_rates.list_rates)
    
    bot.tree.add_command(rate_group)
