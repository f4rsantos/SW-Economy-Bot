from discord import app_commands


class KanbanGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="kanban", description="Kanban board management")


async def setup(bot):
    from commands.kanban import (
        add_task, edit_task, move_task, remove_task,
        view_task, board, overview,
        subtasks, assign, admin, clean,
    )
    from commands.kanban._utils import board_autocomplete, org_autocomplete

    kanban = KanbanGroup()

    add_task.add_task_cmd.autocomplete('board')(board_autocomplete)
    add_task.add_task_cmd.autocomplete('org')(org_autocomplete)
    kanban.add_command(add_task.add_task_cmd)

    edit_task.edit_task_cmd.autocomplete('org')(org_autocomplete)
    kanban.add_command(edit_task.edit_task_cmd)

    move_task.move_task_cmd.autocomplete('board')(board_autocomplete)
    kanban.add_command(move_task.move_task_cmd)

    kanban.add_command(remove_task.remove_task_cmd)
    kanban.add_command(view_task.view_task_cmd)

    board.board_cmd.autocomplete('name')(board_autocomplete)
    board.board_cmd.autocomplete('org')(org_autocomplete)
    kanban.add_command(board.board_cmd)

    overview.overview_cmd.autocomplete('org')(org_autocomplete)
    kanban.add_command(overview.overview_cmd)

    kanban.add_command(subtasks.subtask_add_cmd)
    kanban.add_command(subtasks.subtask_check_cmd)
    kanban.add_command(assign.assign_cmd)
    kanban.add_command(assign.unassign_cmd)

    clean.clean_cmd.autocomplete('org')(org_autocomplete)
    kanban.add_command(clean.clean_cmd)

    kanban.add_command(admin.add_org_cmd)
    kanban.add_command(admin.remove_org_cmd)
    kanban.add_command(admin.list_orgs_cmd)
    kanban.add_command(admin.list_boards_cmd)

    bot.tree.add_command(kanban)
