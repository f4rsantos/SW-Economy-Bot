# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import random

PIRATE_LOSS_MESSAGES = [
    "The pirates cackle as your coin vanishes into the pot. Better luck next raid.",
    "Davy Jones sends his regards, and keeps your wager.",
    "The dealer parrot squawks 'AWK, LOSER' and pockets your stake.",
    "Your treasure map led straight into the house's coffers. Rookie mistake.",
    "The dice, the wheel, the cards, all rigged in the pirates' favor. Shocking, we know.",
    "A one legged deckhand counts your loss twice, just to enjoy it more.",
    "The Kraken ate your winnings before they ever reached your pocket.",
    "You've been keelhauled by fortune itself. Try again, if you dare.",
    "The captain toasts to your generous donation to the ship's fund.",
    "Blackbeard himself couldn't have lost that badly on purpose.",
    "The parrot on the dealer's shoulder is laughing at you. Actually laughing.",
    "Your stake now funds someone else's rum. Cheers to that, at least.",
    "The house wins again. The house always seems to win. Curious, that.",
    "That was a fine wager. It was also a fine loss. Mostly the loss part.",
    "Somewhere, a pirate is buying a new hat with your money. Congratulations.",
    "The cannons fired blanks and so did your luck.",
    "You walked the plank on that one. Financially speaking.",
    "The sea takes what it wants, and today it wanted your treasury.",
    "Even the ship's cat is embarrassed for you right now.",
    "A bad beat, a worse bet, and a very happy quartermaster.",
]


def random_loss_message() -> str:
    return random.choice(PIRATE_LOSS_MESSAGES)


SLOT_SYMBOLS = ['CHERRY', 'BELL', 'SKULL', 'ANCHOR', 'COIN', 'PARROT', 'CHEST']

SLOT_EMOJI = {
    'CHERRY': '\U0001F352',
    'BELL': '\U0001F514',
    'SKULL': '\U0001F480',
    'ANCHOR': '⚓',
    'COIN': '\U0001FA99',
    'PARROT': '\U0001F99C',
    'CHEST': '\U0001F4B0',
}

SLOT_TRIPLE_PAYOUTS = {
    'CHEST': 40,
    'PARROT': 15,
    'COIN': 8,
    'ANCHOR': 5,
    'BELL': 3,
    'CHERRY': 2,
    'SKULL': 0,
}
SLOT_PAYOUTS = SLOT_TRIPLE_PAYOUTS

SLOT_PAIR_PAYOUT = 1.5

BASE_SLOT_WEIGHTS = {
    'CHERRY': 10,
    'BELL': 8,
    'SKULL': 6,
    'ANCHOR': 5,
    'COIN': 3,
    'PARROT': 2,
    'CHEST': 1,
}


def _rtp_for_weights(weights: dict) -> float:
    total = sum(weights.values())
    probs = {s: w / total for s, w in weights.items()}
    triple_rtp = sum((probs[s] ** 3) * SLOT_TRIPLE_PAYOUTS[s] for s in SLOT_SYMBOLS)
    non_skull = [s for s in SLOT_SYMBOLS if s != 'SKULL']
    pair_prob = sum(3 * (probs[a] ** 2) * (1 - probs[a]) for a in non_skull)
    pair_rtp = pair_prob * SLOT_PAIR_PAYOUT
    return triple_rtp + pair_rtp


def slot_weights_for_edge(edge: float) -> dict:
    target_rtp = 1 - edge

    lo, hi = 0.1, 60.0
    for _ in range(80):
        mid = (lo + hi) / 2
        trial = dict(BASE_SLOT_WEIGHTS)
        trial['CHERRY'] = BASE_SLOT_WEIGHTS['CHERRY'] * mid
        trial_rtp = _rtp_for_weights(trial)
        if trial_rtp < target_rtp:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2
    final = dict(BASE_SLOT_WEIGHTS)
    final['CHERRY'] = BASE_SLOT_WEIGHTS['CHERRY'] * mid
    total_final = sum(final.values())
    return {k: v / total_final for k, v in final.items()}


def spin_reel(weights: dict) -> str:
    symbols = list(weights.keys())
    probs = list(weights.values())
    return random.choices(symbols, weights=probs, k=1)[0]


def evaluate_slots(reels: list[str]) -> float:
    if reels[0] == reels[1] == reels[2]:
        return float(SLOT_TRIPLE_PAYOUTS[reels[0]])
    counts = {}
    for r in reels:
        counts[r] = counts.get(r, 0) + 1
    for sym, count in counts.items():
        if count == 2 and sym != 'SKULL':
            return SLOT_PAIR_PAYOUT
    return 0.0


def play_slots(edge: float) -> dict:
    weights = slot_weights_for_edge(edge)
    reels = [spin_reel(weights) for _ in range(3)]
    multiplier = evaluate_slots(reels)
    return {'reels': reels, 'multiplier': multiplier}


ROULETTE_WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
    24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
]

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

ROULETTE_BASE_EDGE = 1 / 37


def roulette_color(pocket: int) -> str:
    if pocket == 0:
        return 'GREEN'
    return 'RED' if pocket in ROULETTE_RED else 'BLACK'


def spin_roulette() -> int:
    return random.choice(ROULETTE_WHEEL_ORDER)


def roulette_payout_multiplier(bet_type: str, bet_value, pocket: int, edge: float) -> float:
    fair_multiplier = {
        'straight': 36,
        'red': 2,
        'black': 2,
        'odd': 2,
        'even': 2,
    }.get(bet_type)
    if fair_multiplier is None:
        raise ValueError(f"Unknown roulette bet type: {bet_type}")

    top_up = max(0.0, edge - ROULETTE_BASE_EDGE)
    adjusted_multiplier = fair_multiplier * (1 - top_up)

    won = False
    if bet_type == 'straight':
        won = pocket == int(bet_value)
    elif bet_type == 'red':
        won = roulette_color(pocket) == 'RED'
    elif bet_type == 'black':
        won = roulette_color(pocket) == 'BLACK'
    elif bet_type == 'odd':
        won = pocket != 0 and pocket % 2 == 1
    elif bet_type == 'even':
        won = pocket != 0 and pocket % 2 == 0

    return adjusted_multiplier if won else 0.0


def play_roulette(bet_type: str, bet_value, edge: float) -> dict:
    pocket = spin_roulette()
    multiplier = roulette_payout_multiplier(bet_type, bet_value, pocket, edge)
    return {'pocket': pocket, 'color': roulette_color(pocket), 'multiplier': multiplier}


def roulette_animation_frames(final_pocket: int, num_frames: int = 5) -> list[list[int]]:
    order = ROULETTE_WHEEL_ORDER
    n = len(order)
    final_idx = order.index(final_pocket)
    frames = []
    step_sizes = [13, 9, 6, 3, 1]
    if num_frames != len(step_sizes):
        step_sizes = step_sizes[:num_frames] or [1] * num_frames
    cursor = (final_idx - sum(step_sizes)) % n
    for step in step_sizes:
        cursor = (cursor + step) % n
        window = [order[(cursor + i) % n] for i in range(-2, 3)]
        frames.append(window)
    frames[-1] = [order[(final_idx + i) % n] for i in range(-2, 3)]
    return frames


CHICKEN_MAX_STEPS = 6

CHICKEN_BASE_SURVIVAL_PROB = [
    0.85, 0.80, 0.75, 0.68, 0.60, 0.52,
]


def chicken_survival_probability(step: int) -> float:
    return CHICKEN_BASE_SURVIVAL_PROB[step - 1]


def chicken_fair_multiplier_at_step(step: int) -> float:
    product = 1.0
    for s in range(1, step + 1):
        product *= chicken_survival_probability(s)
    return 1.0 / product


def chicken_multiplier_at_step(step: int, edge: float) -> float:
    if step == 0:
        return 1.0
    return round(chicken_fair_multiplier_at_step(step) * (1 - edge), 4)


def chicken_resolve_step(step: int) -> bool:
    return random.random() < chicken_survival_probability(step)


def chicken_payout_multiplier(cashout_step: int, edge: float) -> float:
    if cashout_step <= 0:
        return 0.0
    return chicken_multiplier_at_step(cashout_step, edge)


def chicken_max_multiplier(edge: float) -> float:
    return chicken_multiplier_at_step(CHICKEN_MAX_STEPS, edge)


def slot_max_multiplier() -> float:
    return float(max(SLOT_TRIPLE_PAYOUTS.values()))


DICE_FACES = [1, 2, 3, 4, 5, 6]

DICE_EMOJI = {
    1: '⚀',
    2: '⚁',
    3: '⚂',
    4: '⚃',
    5: '⚄',
    6: '⚅',
}

DICE_LOW = {1, 2, 3}
DICE_HIGH = {4, 5, 6}

DICE_HIGH_LOW_FAIR_MULTIPLIER = 2.0
DICE_EXACT_FAIR_MULTIPLIER = 6.0


def roll_die() -> int:
    return random.choice(DICE_FACES)


def dice_payout_multiplier(bet_type: str, bet_value, roll: int, edge: float) -> float:
    fair_multiplier = {
        'high': DICE_HIGH_LOW_FAIR_MULTIPLIER,
        'low': DICE_HIGH_LOW_FAIR_MULTIPLIER,
        'exact': DICE_EXACT_FAIR_MULTIPLIER,
    }.get(bet_type)
    if fair_multiplier is None:
        raise ValueError(f"Unknown dice bet type: {bet_type}")

    adjusted_multiplier = fair_multiplier * (1 - edge)

    won = False
    if bet_type == 'high':
        won = roll in DICE_HIGH
    elif bet_type == 'low':
        won = roll in DICE_LOW
    elif bet_type == 'exact':
        won = roll == int(bet_value)

    return adjusted_multiplier if won else 0.0


def play_dice(bet_type: str, bet_value, edge: float) -> dict:
    roll = roll_die()
    multiplier = dice_payout_multiplier(bet_type, bet_value, roll, edge)
    return {'roll': roll, 'multiplier': multiplier}


def dice_max_multiplier() -> float:
    return DICE_EXACT_FAIR_MULTIPLIER


def dice_roll_animation_frames(final_roll: int, num_frames: int = 4) -> list[int]:
    frames = [roll_die() for _ in range(num_frames - 1)]
    frames.append(final_roll)
    return frames


BLACKJACK_WIN_FAIR_MULTIPLIER = 2.0
BLACKJACK_NATURAL_FAIR_MULTIPLIER = 2.5
BLACKJACK_PUSH_MULTIPLIER = 1.0

CARD_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CARD_SUITS = ['♠', '♥', '♦', '♣']

CARD_RANK_VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10,
}


def blackjack_card_label(card: tuple) -> str:
    rank, suit = card
    return f"{rank}{suit}"


def draw_blackjack_card() -> tuple:
    rank = random.choice(CARD_RANKS)
    suit = random.choice(CARD_SUITS)
    return (rank, suit)


def blackjack_hand_value(hand: list) -> int:
    total = sum(CARD_RANK_VALUES[rank] for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def blackjack_is_soft(hand: list) -> bool:
    total = sum(CARD_RANK_VALUES[rank] for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return aces > 0


def blackjack_is_natural(hand: list) -> bool:
    return len(hand) == 2 and blackjack_hand_value(hand) == 21


def blackjack_win_multiplier(edge: float) -> float:
    return round(BLACKJACK_WIN_FAIR_MULTIPLIER * (1 - edge), 4)


def blackjack_natural_multiplier(edge: float) -> float:
    return round(BLACKJACK_NATURAL_FAIR_MULTIPLIER * (1 - edge), 4)


def blackjack_max_multiplier() -> float:
    return BLACKJACK_NATURAL_FAIR_MULTIPLIER


def blackjack_dealer_should_hit(dealer_hand: list) -> bool:
    return blackjack_hand_value(dealer_hand) < 17


def blackjack_resolve(player_hand: list, dealer_hand: list, edge: float) -> dict:
    player_value = blackjack_hand_value(player_hand)
    dealer_value = blackjack_hand_value(dealer_hand)

    if player_value > 21:
        return {'outcome': 'bust', 'multiplier': 0.0}

    if dealer_value > 21:
        return {'outcome': 'dealer_bust', 'multiplier': blackjack_win_multiplier(edge)}

    if player_value > dealer_value:
        return {'outcome': 'win', 'multiplier': blackjack_win_multiplier(edge)}

    if player_value == dealer_value:
        return {'outcome': 'push', 'multiplier': BLACKJACK_PUSH_MULTIPLIER}

    return {'outcome': 'loss', 'multiplier': 0.0}
