import discord
from discord import app_commands

class BattleGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="battle", description="Battle management commands")

async def setup(bot):
    from commands.battles import (
        battles, startBattle, endBattle, joinBattle,
        leaveBattle
    )
    from commands.units import damageUnit

    battle_group = BattleGroup()

    battle_group.add_command(battles.battles)
    battle_group.add_command(startBattle.start_battle_cmd)
    battle_group.add_command(endBattle.end_battle_cmd)
    battle_group.add_command(joinBattle.join_battle_cmd)
    battle_group.add_command(damageUnit.damage_unit_cmd)
    battle_group.add_command(leaveBattle.leave_battle_cmd)

    bot.tree.add_command(battle_group)
