# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from utils.faction_utils import (
    is_company,
    is_pirate,
    FACTION_TYPE_NATION,
    FACTION_TYPE_COMPANY,
    FACTION_TYPE_PIRATE,
    FACTION_TYPE_LABELS,
)


def test_is_company_only_true_for_type_1():
    assert is_company(FACTION_TYPE_COMPANY) is True
    assert is_company(FACTION_TYPE_NATION) is False
    assert is_company(FACTION_TYPE_PIRATE) is False


def test_is_pirate_only_true_for_type_2():
    assert is_pirate(FACTION_TYPE_PIRATE) is True
    assert is_pirate(FACTION_TYPE_NATION) is False
    assert is_pirate(FACTION_TYPE_COMPANY) is False


def test_labels_cover_all_three_types():
    assert FACTION_TYPE_LABELS[FACTION_TYPE_NATION] == "Nation"
    assert FACTION_TYPE_LABELS[FACTION_TYPE_COMPANY] == "Company"
    assert FACTION_TYPE_LABELS[FACTION_TYPE_PIRATE] == "Pirate"
