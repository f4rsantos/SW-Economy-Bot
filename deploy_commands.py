\
\
\
\
import logging
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info("=" * 70)
        logger.info("SOLAR ECONOMY - Command Deployment")
        logger.info("=" * 70)
        logger.info(f"Bot: {bot.user.name}")
        logger.info(f"ID: {bot.user.id}")

        commands_dir = "commands"
        loaded = []

        if os.path.exists(commands_dir):
            for folder in os.listdir(commands_dir):
                folder_path = os.path.join(commands_dir, folder)
                if not os.path.isdir(folder_path) or folder.startswith('_'):
                    continue
                init_file = os.path.join(folder_path, '__init__.py')
                if os.path.exists(init_file):
                    try:
                        cog_path = f"commands.{folder}"
                        await bot.load_extension(cog_path)
                        loaded.append(cog_path)
                    except Exception as e:
                        logger.error(f"Failed to load {cog_path}: {e}")
                else:
                    for file in os.listdir(folder_path):
                        if file.endswith('.py') and not file.startswith('_') and file != 'info.py':
                            try:
                                cog_path = f"commands.{folder}.{file[:-3]}"
                                await bot.load_extension(cog_path)
                                loaded.append(cog_path)
                            except Exception as e:
                                logger.error(f"Failed to load {cog_path}: {e}")

        logger.info(f"Loaded {len(loaded)} command module(s)")

        logger.info("Syncing commands globally...")
        try:
            synced = await bot.tree.sync()
            logger.info(f"Successfully synced {len(synced)} command(s)")
            logger.info("Commands:")
            for cmd in synced:
                logger.info(f"  /{cmd.name} - {cmd.description}")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        logger.info("=" * 70)
        logger.info("Deployment complete!")
        logger.info("=" * 70)

        await bot.close()
    
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
