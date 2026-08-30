# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from discord import app_commands


class FactionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="faction", description="Faction management commands")


async def setup(bot):
    from commands.faction import (
        list_factions, faction_details, rename_faction, set_leader,
        merge_aux, delete_faction, create_faction, allegiance_requests
    )

    faction_group = FactionGroup()
    faction_group.add_command(list_factions.list_factions)
    faction_group.add_command(faction_details.faction_details)
    faction_group.add_command(rename_faction.rename_faction)
    faction_group.add_command(set_leader.set_leader)
    faction_group.add_command(merge_aux.merge_aux)
    faction_group.add_command(delete_faction.delete_faction)
    faction_group.add_command(create_faction.create_faction)
    faction_group.add_command(allegiance_requests.allegiance_requests)
    faction_group.add_command(allegiance_requests.allegiance_decide)

    bot.tree.add_command(faction_group)
