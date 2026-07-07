import discord
from discord import app_commands
import os
from datetime import datetime, timezone
from utils.embeds import success_embed, error_embed
from services.utility_service import (
    get_operator_for_player,
    get_user_access_row,
    get_public_table_names_for_backup,
    get_all_rows_for_table,
)


@app_commands.command(name="backup", description="Create database backup (Level 10)")
async def backup(interaction: discord.Interaction):
    user_id = interaction.user.id

    operator = await get_operator_for_player(user_id)
    user = await get_user_access_row(user_id)
    access_level = user['access_level'] if user else 0

    if access_level < 10 and not operator:
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    await interaction.response.defer()

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.sql"
        backup_path = os.path.join(os.getcwd(), backup_file)

        table_names = await get_public_table_names_for_backup()
        tables = [{'tablename': t} for t in table_names]
        if not tables:
            await interaction.followup.send(embed=error_embed("Error", "No tables found to backup."))
            return

        sql_content = [
            "-- Database Backup",
            f"-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "-- Excludes: auths, operators\n"
        ]
        total_rows = 0

        for table_row in tables:
            table_name = table_row['tablename']
            rows = await get_all_rows_for_table(table_name)
            total_rows += len(rows)
            sql_content.append(f"\n-- Table: {table_name}")

            if rows:
                col_names = list(rows[0].keys())
                for row in rows:
                    values = []
                    for col in col_names:
                        val = row[col]
                        if val is None:
                            values.append('NULL')
                        elif isinstance(val, str):
                            values.append(f"'{val.replace(chr(39), chr(39)*2)}'")
                        elif isinstance(val, bool):
                            values.append('true' if val else 'false')
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        else:
                            values.append(f"'{str(val).replace(chr(39), chr(39)*2)}'")
                    sql_content.append(f"INSERT INTO {table_name} ({', '.join(col_names)}) VALUES ({', '.join(values)});")

        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sql_content))

        file_size = os.path.getsize(backup_path)
        if not file_size:
            await interaction.followup.send(embed=error_embed("Error", "Backup file was not created or is empty."))
            return

        if file_size > 25 * 1024 * 1024:
            os.remove(backup_path)
            await interaction.followup.send(embed=error_embed("Error", f"Backup file too large ({file_size / (1024*1024):.2f} MB). Maximum 25 MB."))
            return

        embed = success_embed("Database Backup", f"**File:** {backup_file}\n**Size:** {file_size / (1024*1024):.2f} MB\n**Rows:** {total_rows:,}\n**Tables:** {len(tables)}\n**Time:** {timestamp}")
        with open(backup_path, 'rb') as f:
            await interaction.followup.send(embed=embed, file=discord.File(f, filename=backup_file))
        os.remove(backup_path)

    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Backup failed: {str(e)}"))


async def setup(bot):
    bot.tree.add_command(backup)
