import discord
from discord import app_commands

class MapGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="map", description="Map and territory management commands")

async def setup(bot):
    from commands.map import (
        land, claimHex, unclaimHex, view,
        addPlace, deletePlace, renamePlace, modifyPlace
    )
    
    map_group = MapGroup()
    
    map_group.add_command(land.land)
    map_group.add_command(claimHex.claim_hex)
    map_group.add_command(unclaimHex.unclaim_hex)
    map_group.add_command(view.view)
    map_group.add_command(addPlace.add_place)
    map_group.add_command(deletePlace.delete_place)
    map_group.add_command(renamePlace.rename_place)
    map_group.add_command(modifyPlace.modify_place)
    
    bot.tree.add_command(map_group)
