import discord
from discord import app_commands

class PactGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="pact", description="Diplomatic pact commands")

async def setup(bot):
    from commands.diplomacy import (
        pacts, create_pact, join_pact, leave_pact, end_pact, remove_member, pact_types
    )

    pact_group = PactGroup()

    pact_group.add_command(pacts.pacts)
    pact_group.add_command(create_pact.create_pact)
    pact_group.add_command(join_pact.join_pact)
    pact_group.add_command(leave_pact.leave_pact)
    pact_group.add_command(end_pact.end_pact)
    pact_group.add_command(remove_member.remove_member)
    pact_group.add_command(pact_types.pact_types)
    
    bot.tree.add_command(pact_group)
