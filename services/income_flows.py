# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Dict


def storage_overflow(stock: int, amount: int, capacity: int) -> int:
    return max(0, stock + amount - capacity)


def gross_production(preview: Dict, include_refined: bool, refund: Dict[str, int] = None) -> Dict[str, int]:
    produced: Dict[str, int] = {}
    for data in preview.get('worlds', {}).values():
        sources = [data.get('unrefined_production', {})]
        if include_refined:
            sources.append(data.get('refined_production', {}))
        for source in sources:
            for name, amount in source.items():
                if amount > 0:
                    produced[name] = produced.get(name, 0) + int(amount)
    for name, amount in (refund or {}).items():
        if amount > 0:
            produced[name] = produced.get(name, 0) + int(amount)
    return produced
