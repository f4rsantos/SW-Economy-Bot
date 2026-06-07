import discord
from discord import app_commands

class BlockadeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="blockade", description="Blockade management commands")

async def setup(bot):
    from commands.blockades import blockades, startBlockade, endBlockade
    
    blockade_group = BlockadeGroup()
    
    blockade_group.add_command(blockades.blockades)
    blockade_group.add_command(startBlockade.start_blockade_cmd)
    blockade_group.add_command(endBlockade.end_blockade_cmd)
    
    bot.tree.add_command(blockade_group)
