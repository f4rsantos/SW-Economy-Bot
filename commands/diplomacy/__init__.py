import discord
from discord import app_commands

class PactGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="pact", description="Diplomatic pact commands")

async def setup(bot):
    from commands.diplomacy import (
        pacts, createPact, joinPact, leavePact, endPact, removeMember, pactTypes
    )
    
    pact_group = PactGroup()
    
    pact_group.add_command(pacts.pacts)
    pact_group.add_command(createPact.create_pact)
    pact_group.add_command(joinPact.join_pact)
    pact_group.add_command(leavePact.leave_pact)
    pact_group.add_command(endPact.end_pact)
    pact_group.add_command(removeMember.remove_member)
    pact_group.add_command(pactTypes.pact_types)
    
    bot.tree.add_command(pact_group)
