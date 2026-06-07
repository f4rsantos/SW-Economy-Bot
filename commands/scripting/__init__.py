import discord
from discord import app_commands


class ScriptGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="script", description="Faction automation scripts")


async def setup(bot):
    from commands.scripting import add, list_scripts, info, edit, delete, test, trigger

    group = ScriptGroup()
    group.add_command(add.script_add)
    group.add_command(list_scripts.script_list)
    group.add_command(info.script_info)
    group.add_command(edit.script_edit)
    group.add_command(delete.script_delete)
    group.add_command(test.script_test)
    group.add_command(trigger.script_trigger)

    bot.tree.add_command(group)
