# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from services.income_flows import gross_production, storage_overflow


def test_storage_overflow_matches_clamp():
    assert storage_overflow(80, 30, 100) == 10
    assert storage_overflow(10, 30, 100) == 0
    assert storage_overflow(50, -20, 100) == 0
    assert storage_overflow(0, 500, 0) == 500


def test_gross_production_sums_extraction_refining_and_refund():
    preview = {'worlds': {
        1: {'unrefined_production': {'U-CS': 100, 'U-CM': 0}, 'refined_production': {'CS': 300}},
        2: {'unrefined_production': {'U-CS': 50}},
    }}
    assert gross_production(preview, True, {'CM': 7}) == {'U-CS': 150, 'CS': 300, 'CM': 7}
    assert gross_production(preview, False) == {'U-CS': 150}
