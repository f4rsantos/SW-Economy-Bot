# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

_active_games: dict[int, str] = {}


def start_game(user_id: int, game_name: str):
    if user_id in _active_games:
        raise ValueError(f"GAME_IN_PROGRESS: You already have a {_active_games[user_id]} game in progress. Finish it first.")
    _active_games[user_id] = game_name


def end_game(user_id: int):
    _active_games.pop(user_id, None)


def has_active_game(user_id: int) -> bool:
    return user_id in _active_games
