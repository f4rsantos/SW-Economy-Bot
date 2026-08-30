# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands

class BlockadeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="blockade", description="Blockade management commands")

async def setup(bot):
    from commands.blockades import blockades, start_blockade, end_blockade

    blockade_group = BlockadeGroup()

    blockade_group.add_command(blockades.blockades)
    blockade_group.add_command(start_blockade.start_blockade_cmd)
    blockade_group.add_command(end_blockade.end_blockade_cmd)
    
    bot.tree.add_command(blockade_group)
