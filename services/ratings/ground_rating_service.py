# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Dict
import math

_ARMOR_COSTS = {
    'heavy':  {'ER': 24,  'CM': 90,  'EL': 30,   'CS': 40},
    'medium': {'ER': 26,  'CM': 50,  'EL': 20,   'CS': 30},
    'light':  {'ER': 40,  'CM': 30,  'EL': 12.5, 'CS': 20},
    'none':   {'ER': 100, 'CM': 20,  'EL': 10,   'CS': 10}
}
_PROT_COSTS = {
    'both': {'ER': 0.3, 'CM': 20, 'EL': 25},
    'hard': {'ER': 0.15, 'CM': 10, 'EL': 10},
    'soft': {'ER': 0.1, 'CM': 5,  'EL': 15},
    'none': {'ER': 0,   'CM': 0,  'EL': 0}
}


def calculate_er(values: Dict) -> float:
    length = values.get('length', 0)
    armor = values.get('armor', 'none')
    protection = values.get('protection', 'none')
    heavy = values.get('heavy', 0)
    medium = values.get('medium', 0)
    light = values.get('light', 0)
    rocket = values.get('rocket', 0)
    systems = values.get('systems', 0)
    shield = values.get('shield', False)
    weapon_system_cost = 7 if heavy > 0 else (3 if medium > 0 else 0)
    length_cost = (length ** 2) / (_ARMOR_COSTS[armor]['ER'] - weapon_system_cost)
    system_cost = 1 + systems * 0.1 + _PROT_COSTS[protection]['ER']
    return math.ceil(system_cost * (
        length_cost + heavy * 0.9 + medium * 0.3 + light * 0.03 +
        rocket * 0.08 + (1 if shield else 0)
    ) * 100) / 100


def calculate_cm(values: Dict) -> float:
    length = values.get('length', 0)
    armor = values.get('armor', 'none')
    protection = values.get('protection', 'none')
    heavy = values.get('heavy', 0)
    medium = values.get('medium', 0)
    light = values.get('light', 0)
    rocket = values.get('rocket', 0)
    shield = values.get('shield', False)
    systems = values.get('systems', 0)
    length_cost = (length ** 2) / 8.5 + _ARMOR_COSTS[armor]['CM'] + _PROT_COSTS[protection]['CM']
    return math.ceil((systems + 1) * (
        length_cost + heavy * 10 + medium * 2 + light * 0.3 + rocket + (25 if shield else 0)
    ) * 20) / 100


def calculate_el(values: Dict) -> float:
    length = values.get('length', 0)
    armor = values.get('armor', 'none')
    protection = values.get('protection', 'none')
    heavy = values.get('heavy', 0)
    medium = values.get('medium', 0)
    light = values.get('light', 0)
    rocket = values.get('rocket', 0)
    shield = values.get('shield', False)
    systems = values.get('systems', 0)
    length_cost = 3 * ((length ** 2) / 85 + _ARMOR_COSTS[armor]['EL'] + _PROT_COSTS[protection]['EL'])
    system_cost = systems * 1.5 + 1
    base = system_cost * (length_cost + heavy * 6 + medium * 10 + light * 0.2 + rocket * 0.2)
    return math.ceil(((base * 1.1 + 150) if shield else base) * 20) / 100


def calculate_cs(values: Dict, cost_cm: float, cost_el: float) -> float:
    armor = values.get('armor', 'none')
    heavy = values.get('heavy', 0)
    medium = values.get('medium', 0)
    light = values.get('light', 0)
    rocket = values.get('rocket', 0)
    systems = values.get('systems', 0)
    if heavy > 0 or rocket > 0:
        length_cost = 50
    elif medium > 0:
        length_cost = 30
    elif light > 0:
        length_cost = 15
    else:
        length_cost = 10
    if _ARMOR_COSTS[armor]['CS'] > length_cost:
        length_cost = _ARMOR_COSTS[armor]['CS']
    return math.ceil((length_cost + systems * 2.5 + 0.1 * (cost_cm + cost_el)) * 20) / 100


def rate_ground_vehicle(data: Dict) -> Dict[str, int]:
    cost_cm = calculate_cm(data)
    cost_el = calculate_el(data)
    return {
        'ER': int(calculate_er(data) * 1000000),
        'CM': int(cost_cm),
        'CS': int(calculate_cs(data, cost_cm, cost_el)),
        'EL': int(cost_el)
    }
