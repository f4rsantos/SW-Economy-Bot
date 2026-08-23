# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import queue
import random
import sys
import threading
import time

import httpx

import auth
import services.credential_store as credential_store

_command_queue: "queue.Queue[str]" = queue.Queue()
_started_at = time.monotonic()

_pet_state: dict[int, dict] = {}
_blackjack_credits: dict[int, int] = {}
_blackjack_hands: dict[int, dict] = {}

_DEFAULT_CREDITS = 1000

_JOKE_API_URL = "https://v2.jokeapi.dev/joke/Programming,Miscellaneous?blacklistFlags=nsfw,racist,sexist,explicit,religious,political&safe-mode"

_FALLBACK_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "There are 10 types of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, sees two tables, and asks: can I join you?",
    "Why did the developer go broke? Because he used up all his cache.",
    "I told my computer I needed a break. Now it won't stop sending me Kit-Kats.",
]

_PET_SPECIES = ["slime", "duck", "golem", "penguin", "cat", "crab", "owl", "fox"]
_PET_RARITIES = [
    ("common", 0.50),
    ("uncommon", 0.25),
    ("rare", 0.15),
    ("epic", 0.08),
    ("legendary", 0.02),
]

_PET_ART = {
    "slime": r"""
  .-""-.
 /  o o \
 \  ~~  /
  `----'
""",
    "duck": r"""
   __
  <(o )___
   ( ._> /
    `---'
""",
    "golem": r"""
  [######]
  [ O  O ]
  [  --  ]
  [______]
""",
    "penguin": r"""
   .--.
  ( o.o )
  /| - |\
   ^^ ^^
""",
    "cat": r"""
  /\_/\
 ( o.o )
  > ^ <
""",
    "crab": r"""
  (\./)  (\./)
   ( . . )
  c(")(")d
""",
    "owl": r"""
   ,_,
  (o,o)
  (   )
  -"-"-
""",
    "fox": r"""
   /\   /\
  /  \_/  \
 (  o   o  )
  \   ~   /
   `-----'
""",
}

_RARITY_FRAME = {
    "common": ("", ""),
    "uncommon": ("~ ", " ~"),
    "rare": ("* ", " *"),
    "epic": ("# ", " #"),
    "legendary": ("$ ", " $"),
}


def _render_pet_art(species: str, rarity: str) -> str:
    art = _PET_ART[species]
    left, right = _RARITY_FRAME[rarity]
    if not left and not right:
        return art
    lines = art.strip("\n").split("\n")
    framed = "\n".join(f"{left}{line}{right}" for line in lines)
    return f"\n{framed}\n"


def start(bot) -> None:
    thread = threading.Thread(target=_read_stdin, daemon=True)
    thread.start()
    bot.loop.create_task(_drain_loop(bot))


def _read_stdin() -> None:
    for line in sys.stdin:
        _command_queue.put(line.strip())


async def _drain_loop(bot) -> None:
    while True:
        try:
            line = _command_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.2)
            continue
        if line:
            await _dispatch(bot, line)


async def _dispatch(bot, line: str) -> None:
    parts = line.split()
    if not parts:
        return
    name = parts[0].lower()
    args = parts[1:]
    handler = _COMMANDS.get(name)
    if handler is None:
        print(f"Unknown command: {name}. Type 'help' for a list.")
        return
    try:
        await handler(bot, args)
    except Exception as e:
        print(f"Command '{name}' failed: {type(e).__name__}: {e}")


def _operator_id() -> int:
    return auth.operator_discord_id or 0


def _roll_rarity() -> str:
    roll = random.random()
    cumulative = 0.0
    for name, weight in _PET_RARITIES:
        cumulative += weight
        if roll < cumulative:
            return name
    return _PET_RARITIES[-1][0]


async def _cmd_exit(bot, args: list[str]) -> None:
    import bot as bot_module
    bot_module.request_terminal_shutdown()
    print("Shutting down...")
    await bot.close()


async def _cmd_help(bot, args: list[str]) -> None:
    print("Available commands:")
    print("  exit              shut down the bot gracefully")
    print("  help              show this list")
    print("  status            show uptime, guild count, latency")
    print("  login save        save current license key and Discord ID for auto-login")
    print("  login clear       remove saved auto-login credentials")
    print("  login status      show saved auto-login credential status")
    print("  blackjack <bet>   play a hand of blackjack vs the dealer")
    print("  hit / stand       act on your current blackjack hand")
    print("  42                the answer")
    print("  coffee            brew a virtual coffee and hear a joke")
    print("  pet spawn [species]  roll a pet for this session (once only)")
    print("  pet               show your pet")
    print("  pet feed          feed your pet")
    print("  pet pet           pet your pet")


async def _cmd_login(bot, args: list[str]) -> None:
    sub = args[0].lower() if args else ""

    if sub == "save":
        if not auth.operator_license_key or not auth.operator_discord_id:
            print("Cannot save credentials: not currently authenticated with a license key.")
            return
        if credential_store.save_credentials(auth.operator_license_key, auth.operator_discord_id):
            print("Credentials saved. Auto-login enabled for 30 days.")
        else:
            print("Failed to save credentials.")
        return

    if sub == "clear":
        if credential_store.clear_credentials():
            print("Saved credentials cleared.")
        else:
            print("No saved credentials to clear.")
        return

    if sub == "status":
        status = credential_store.credentials_status()
        if not status["exists"]:
            print("No saved credentials.")
            return
        print(f"Saved credentials for Discord ID: {status['discord_id']}")
        print(f"Days remaining: {status['days_remaining']}")
        return

    print("Usage: login save | login clear | login status")


async def _cmd_status(bot, args: list[str]) -> None:
    uptime = time.monotonic() - _started_at
    hours, rem = divmod(int(uptime), 3600)
    minutes, seconds = divmod(rem, 60)
    print(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")
    print(f"Guilds: {len(bot.guilds)}")
    print(f"Latency: {bot.latency * 1000:.1f} ms")


def _draw_card() -> int:
    return random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11])


def _hand_value(cards: list[int]) -> int:
    total = sum(cards)
    aces = cards.count(11)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


async def _cmd_blackjack(bot, args: list[str]) -> None:
    operator_id = _operator_id()
    balance = _blackjack_credits.setdefault(operator_id, _DEFAULT_CREDITS)

    if operator_id in _blackjack_hands:
        print("You already have a hand in progress. Type 'hit' or 'stand'.")
        return

    if not args:
        print(f"Session credits: {balance}. Usage: blackjack <bet>")
        return

    try:
        bet = int(args[0])
    except ValueError:
        print("Bet must be a whole number.")
        return

    if bet <= 0:
        print("Bet must be positive.")
        return

    if bet > balance:
        print(f"Not enough session credits. You have {balance}.")
        return

    player = [_draw_card(), _draw_card()]
    dealer = [_draw_card(), _draw_card()]
    _blackjack_hands[operator_id] = {"player": player, "dealer": dealer, "bet": bet}

    print(f"Your hand: {player} ({_hand_value(player)})")
    print(f"Dealer shows: {dealer[0]}")

    if _hand_value(player) == 21:
        await _resolve_blackjack(operator_id)
        return

    print("Type 'hit' or 'stand'.")


async def _cmd_hit(bot, args: list[str]) -> None:
    operator_id = _operator_id()
    hand = _blackjack_hands.get(operator_id)
    if hand is None:
        print("No blackjack hand in progress. Start one with: blackjack <bet>")
        return

    hand["player"].append(_draw_card())
    value = _hand_value(hand["player"])
    print(f"Your hand: {hand['player']} ({value})")

    if value >= 21:
        await _resolve_blackjack(operator_id)


async def _cmd_stand(bot, args: list[str]) -> None:
    operator_id = _operator_id()
    if operator_id not in _blackjack_hands:
        print("No blackjack hand in progress. Start one with: blackjack <bet>")
        return
    await _resolve_blackjack(operator_id)


async def _resolve_blackjack(operator_id: int) -> None:
    hand = _blackjack_hands.pop(operator_id)
    player_value = _hand_value(hand["player"])
    dealer = hand["dealer"]
    bet = hand["bet"]

    if player_value > 21:
        _blackjack_credits[operator_id] -= bet
        print(f"Bust. You lose {bet}. Balance: {_blackjack_credits[operator_id]}")
        return

    while _hand_value(dealer) < 17:
        dealer.append(_draw_card())

    dealer_value = _hand_value(dealer)
    print(f"Dealer hand: {dealer} ({dealer_value})")

    if dealer_value > 21 or player_value > dealer_value:
        _blackjack_credits[operator_id] += bet
        print(f"You win {bet}. Balance: {_blackjack_credits[operator_id]}")
    elif player_value == dealer_value:
        print(f"Push. Balance: {_blackjack_credits[operator_id]}")
    else:
        _blackjack_credits[operator_id] -= bet
        print(f"You lose {bet}. Balance: {_blackjack_credits[operator_id]}")


async def _cmd_42(bot, args: list[str]) -> None:
    print("The answer to life, the universe, and everything.")


async def _cmd_coffee(bot, args: list[str]) -> None:
    print(r"""
    ( (
     ) )
  ........
  |      |]
  \      /
   `----'
""")
    joke = await _fetch_joke()
    print(joke)


async def _fetch_joke() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(_JOKE_API_URL)
            resp.raise_for_status()
            data = resp.json()
            if data.get("type") == "twopart":
                return f"{data['setup']} ... {data['delivery']}"
            return data.get("joke", random.choice(_FALLBACK_JOKES))
    except Exception:
        return random.choice(_FALLBACK_JOKES)


async def _cmd_pet(bot, args: list[str]) -> None:
    operator_id = _operator_id()
    sub = args[0].lower() if args else ""

    if sub == "spawn":
        if operator_id in _pet_state:
            pet = _pet_state[operator_id]
            print(f"You already spawned a pet this session: {pet['rarity']} {pet['species']}.")
            return

        requested_species = args[1].lower() if len(args) > 1 else None
        if requested_species and requested_species not in _PET_SPECIES:
            print(f"Unknown species. Choose from: {', '.join(_PET_SPECIES)}")
            return

        species = requested_species or random.choice(_PET_SPECIES)
        rarity = _roll_rarity()
        _pet_state[operator_id] = {
            "species": species,
            "rarity": rarity,
            "hunger": 0,
            "last_fed": time.monotonic(),
            "pets_received": 0,
        }
        print(f"A {rarity} {species} appeared.")
        return

    pet = _pet_state.get(operator_id)
    if pet is None:
        print("You don't have a pet yet. Try: pet spawn [species]")
        return

    if sub == "feed":
        pet["hunger"] = 0
        pet["last_fed"] = time.monotonic()
        print(f"Your {pet['rarity']} {pet['species']} is full and happy.")
        return

    if sub == "pet":
        pet["pets_received"] += 1
        print(f"You pet your {pet['rarity']} {pet['species']}. It nuzzles back. ({pet['pets_received']} pets so far)")
        return

    elapsed = time.monotonic() - pet["last_fed"]
    hunger = min(100, int(elapsed / 6))
    mood = "content" if hunger < 30 else "hungry" if hunger < 70 else "starving"
    print(_render_pet_art(pet["species"], pet["rarity"]))
    print(f"{pet['rarity'].upper()} {pet['species']} — hunger: {hunger}/100, mood: {mood}, pets received: {pet['pets_received']}")


_COMMANDS = {
    "exit": _cmd_exit,
    "help": _cmd_help,
    "status": _cmd_status,
    "login": _cmd_login,
    "blackjack": _cmd_blackjack,
    "hit": _cmd_hit,
    "stand": _cmd_stand,
    "42": _cmd_42,
    "coffee": _cmd_coffee,
    "pet": _cmd_pet,
}
