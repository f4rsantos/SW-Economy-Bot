# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def load_bot_config():
    bundle_dir = get_bundle_dir()
    env_path = bundle_dir / ".env"
    if not env_path.exists():
        env_path = Path(".env")
        if not env_path.exists():
            return False
    load_dotenv(env_path)
    return True
