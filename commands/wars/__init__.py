import discord
from discord import app_commands

class WarGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="war", description="War management commands")

async def setup(bot):
    from commands.wars import wars, createWar, joinWar, endWar, leaveWar
    
    war_group = WarGroup()
    
    war_group.add_command(wars.wars)
    war_group.add_command(createWar.create_war_cmd)
    war_group.add_command(joinWar.join_war)
    war_group.add_command(endWar.end_war_cmd)
    war_group.add_command(leaveWar.leave_war)
    
    bot.tree.add_command(war_group)
