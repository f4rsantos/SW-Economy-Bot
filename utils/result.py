# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional

T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    ok: bool
    data: Optional[T] = field(default=None)
    error: Optional[str] = field(default=None)

    @staticmethod
    def success(data: T = None) -> 'Result[T]':
        return Result(ok=True, data=data)

    @staticmethod
    def fail(error: str) -> 'Result':
        return Result(ok=False, error=error)
