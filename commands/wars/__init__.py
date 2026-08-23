# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands

class WarGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="war", description="War management commands")

async def setup(bot):
    from commands.wars import wars, create_war, join_war, end_war, leave_war

    war_group = WarGroup()

    war_group.add_command(wars.wars)
    war_group.add_command(create_war.create_war_cmd)
    war_group.add_command(join_war.join_war)
    war_group.add_command(end_war.end_war_cmd)
    war_group.add_command(leave_war.leave_war)
    
    bot.tree.add_command(war_group)
