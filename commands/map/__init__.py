import discord
from discord import app_commands

class MapGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="map", description="Map and territory management commands")

async def setup(bot):
    from commands.map import (
        land, claim_hex, unclaim_hex, view,
        add_place, delete_place, rename_place, modify_place
    )

    map_group = MapGroup()

    map_group.add_command(land.land)
    map_group.add_command(claim_hex.claim_hex)
    map_group.add_command(unclaim_hex.unclaim_hex)
    map_group.add_command(view.view)
    map_group.add_command(add_place.add_place)
    map_group.add_command(delete_place.delete_place)
    map_group.add_command(rename_place.rename_place)
    map_group.add_command(modify_place.modify_place)
    
    bot.tree.add_command(map_group)
