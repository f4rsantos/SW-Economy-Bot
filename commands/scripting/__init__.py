# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands


class ScriptGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="script", description="Faction automation scripts")


async def setup(bot):
    from commands.scripting import add, list_scripts, info, edit, delete, test, trigger, auto_econ

    group = ScriptGroup()
    group.add_command(add.script_add)
    group.add_command(list_scripts.script_list)
    group.add_command(info.script_info)
    group.add_command(edit.script_edit)
    group.add_command(delete.script_delete)
    group.add_command(test.script_test)
    group.add_command(trigger.script_trigger)
    group.add_command(auto_econ.script_auto_econ)

    bot.tree.add_command(group)
