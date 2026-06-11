import discord
from discord import app_commands

class BattleGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="battle", description="Battle management commands")

async def setup(bot):
    from commands.battles import (
        battles, start_battle, end_battle, join_battle,
        leave_battle
    )
    from commands.units import damage_unit

    battle_group = BattleGroup()

    battle_group.add_command(battles.battles)
    battle_group.add_command(start_battle.start_battle_cmd)
    battle_group.add_command(end_battle.end_battle_cmd)
    battle_group.add_command(join_battle.join_battle_cmd)
    battle_group.add_command(damage_unit.damage_unit_cmd)
    battle_group.add_command(leave_battle.leave_battle_cmd)

    bot.tree.add_command(battle_group)
