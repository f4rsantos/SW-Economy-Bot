from discord import app_commands


class FactionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="faction", description="Faction management commands")


async def setup(bot):
    from commands.faction import (
        listFactions, factionDetails, renameFaction, setLeader,
        mergeAux, deleteFaction, createFaction
    )

    faction_group = FactionGroup()
    faction_group.add_command(listFactions.list_factions)
    faction_group.add_command(factionDetails.faction_details)
    faction_group.add_command(renameFaction.rename_faction)
    faction_group.add_command(setLeader.set_leader)
    faction_group.add_command(mergeAux.merge_aux)
    faction_group.add_command(deleteFaction.delete_faction)
    faction_group.add_command(createFaction.create_faction)

    bot.tree.add_command(faction_group)
