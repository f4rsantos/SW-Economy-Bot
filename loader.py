import os
import sys
from pathlib import Path


async def load_commands(bot):
    commands_dir = Path("commands")
    loaded_count = 0

    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            commands_dir = Path(sys._MEIPASS) / "commands"

    if commands_dir.exists():
        for folder in commands_dir.iterdir():
            if folder.is_dir() and not folder.name.startswith('_'):
                init_file = folder / '__init__.py'
                if init_file.exists():
                    module_path = f"commands.{folder.name}"
                    try:
                        await bot.load_extension(module_path)
                        print(f"  ✓ Loaded group: {folder.name}")
                        loaded_count += 1
                    except Exception as e:
                        print(f"  ✗ Failed to load group {folder.name}: {e}")
                else:
                    for file in folder.iterdir():
                        if file.suffix == '.py' and not file.name.startswith('_'):
                            if file.stem == 'info':
                                continue
                            module_path = f"commands.{folder.name}.{file.stem}"
                            await bot.load_extension(module_path)
                            loaded_count += 1
    else:
        print(f"Commands directory not found: {commands_dir}")

    print(f"Loaded {loaded_count} command module(s)")
