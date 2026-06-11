import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.ERROR,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logging.getLogger(__name__).setLevel(logging.INFO)
logger = logging.getLogger(__name__)

from supabase import create_client
from dotenv import load_dotenv
import asyncio


def get_bundle_dir() -> Path:
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    return Path(__file__).parent


bundle_dir = get_bundle_dir()

if getattr(sys, 'frozen', False):
    try:
        from _credentials import get_credential, is_secure_mode
        if is_secure_mode():
            for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "DISCORD_TOKEN", "DATABASE_URL", "BOT_VERSION"):
                val = get_credential(key)
                if val:
                    os.environ[key] = val
        else:
            raise ImportError("Not in secure mode")
    except (ImportError, Exception):
        env_path = bundle_dir / ".env"
        load_dotenv(env_path if env_path.exists() else None, override=True)
else:
    env_path = bundle_dir / ".env"
    load_dotenv(env_path if env_path.exists() else None, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

_continuity_mode = '-c' in sys.argv
_no_income = '--no-income' in sys.argv


def print_header():
    version = os.getenv("BOT_VERSION", "")
    byline = f"v{version}" if version else "v unknown"
    print("=" * 70)
    print("SOLAR ECONOMY".center(70))
    print(byline.center(70))
    print("=" * 70)
    print()
    if getattr(sys, 'frozen', False):
        print("Loading... (This may take a moment on first run)")
        print()


def validate_environment():
    missing = [k for k, v in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
        "DISCORD_TOKEN": DISCORD_TOKEN,
    }.items() if not v]
    if missing:
        print("ERROR: Configuration missing.")
        if getattr(sys, 'frozen', False):
            print("Please contact the administrator for a properly configured build.")
        else:
            print(f"Missing: {', '.join(missing)}")
            print("Create a .env file in the project root with your credentials.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)


async def force_income(faction_name: str):
    from database.db_manager import db
    from services.income_service import execute_income

    logger.info("=" * 70)
    logger.info(" " * 20 + "FORCING INCOME PROCESSING")
    logger.info("=" * 70)
    await db.connect()
    try:
        if faction_name == 'ALL':
            factions = await db.fetch("SELECT id, name FROM factions ORDER BY name")
            if not factions:
                logger.info("No factions found.")
                return
            statuses = await db.fetch("SELECT id, name FROM fleet_status")
            resources = await db.fetch("SELECT id, name FROM resources")
            shared_cache = {
                'status_ids': {s['name'].lower(): s['id'] for s in statuses},
                'resource_map': {r['name']: r['id'] for r in resources},
            }
            success_count = fail_count = 0
            for faction in factions:
                try:
                    logger.info(f"  Processing: {faction['name']}...")
                    await execute_income(faction['id'], shared_cache)
                    logger.info(f"  ✓ {faction['name']}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"  ✗ {faction['name']}: {e}")
                    fail_count += 1
            logger.info(f"Completed: {success_count} ok, {fail_count} failed")
        else:
            faction = await db.fetchrow(
                "SELECT id, name FROM factions WHERE LOWER(name) = LOWER($1) OR LOWER(formal_name) = LOWER($1)",
                faction_name
            )
            if not faction:
                logger.info(f"Faction '{faction_name}' not found.")
                return
            logger.info(f"Processing: {faction['name']}...")
            await execute_income(faction['id'])
            logger.info("✓ Complete")
        logger.info("=" * 70)
        logger.info(" " * 25 + "INCOME PROCESSED")
        logger.info("=" * 70)
    except Exception as e:
        logger.exception(f"ERROR in force_income: {e}")
    finally:
        await db.disconnect()


def main():
    print_header()
    validate_environment()

    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception:
        print("ERROR: Failed to initialize Supabase client.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    import auth
    auth.init(bundle_dir, supabase_client)

    if not auth.run_oauth(logger):
        sys.exit(1)

    if not auth.verify_license():
        sys.exit(1)

    from bot import start_bot, is_shutdown_intentional

    RESTART_DELAY = 30
    while True:
        start_bot(supabase_client, auth.supabase_user_uuid, _continuity_mode, _no_income)
        if is_shutdown_intentional():
            print()
            print("Goodbye.")
            break
        print()
        print("=" * 60)
        print(f"  Bot crashed. Restarting in {RESTART_DELAY} seconds...")
        print("  Press Ctrl+C to abort restart.")
        print("=" * 60)
        print()
        try:
            for i in range(RESTART_DELAY, 0, -1):
                print(f"\r  Restarting in {i}s...  ", end="", flush=True)
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            print()
            print("Restart aborted. Goodbye.")
            break


if __name__ == "__main__":
    main()
