# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HighScore:
    user_id: int
    score: int

    @classmethod
    def from_row(cls, row) -> "HighScore":
        return cls(user_id=row["user_id"], score=row["score"])
