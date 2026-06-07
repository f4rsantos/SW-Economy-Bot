import discord
from discord import app_commands

class RateGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="rates", description="Vehicle and construct rating commands")

async def setup(bot):
    from commands.constructs import (
        airRate, shipRate, groundRate, infantryRate, missileRate, listRates
    )
    
    rate_group = RateGroup()
    
    rate_group.add_command(airRate.air_rate)
    rate_group.add_command(shipRate.ship_rate)
    rate_group.add_command(groundRate.ground_rate)
    rate_group.add_command(infantryRate.infantry_rate)
    rate_group.add_command(missileRate.missile_rate)
    rate_group.add_command(listRates.list_rates)
    
    bot.tree.add_command(rate_group)
