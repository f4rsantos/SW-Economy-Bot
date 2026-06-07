from typing import Dict

_PRIMARY_COSTS = {
    'assaultrifle': 1, 'machinegun': 50, 'sniperrifle': 1, 'sword': 15, 'staff': 30
}
_SECONDARY_COSTS = {
    'pistol': 0.5, 'shotgun': 0.675, 'rocketlauncher': 15, 'missilelauncher': 125, 'knife': 0.05
}
_CAMO_COSTS = {'active': 25, 'semiactive': 1, 'regular': 0.1, 'none': 0}


def calculate_infantry_cost(values: Dict) -> int:
    species = values.get('species', 'human')
    special_forces = values.get('special_forces', False)
    chemical_adaptations = values.get('chemical_adaptations', 0)
    physical_adaptations = values.get('physical_adaptations', 0)
    power_suit = values.get('power_suit', False)
    armor = values.get('armor', 0)
    camouflage = values.get('camouflage', 'none')
    shield = values.get('shield', False)
    grenades = values.get('grenades', 0)
    missiles = values.get('missiles', 0)
    rockets = values.get('rockets', 0)
    primary = values.get('primary', 'assaultrifle')
    secondary = values.get('secondary', None)
    other = values.get('other', 0)

    body_cost = 10 if species == 'human' else 100
    special_cost = 1.1 if special_forces else 1.0
    armor_cost = armor + 1

    total = (
        body_cost
        + chemical_adaptations * 15
        + physical_adaptations * 25
        + (50 if power_suit else 0)
        + armor_cost
        + (5 if shield else 0)
        + _CAMO_COSTS.get(camouflage, 0)
        + grenades * 0.05
        + missiles * 5
        + rockets * 1
        + _PRIMARY_COSTS.get(primary, 0)
        + (_SECONDARY_COSTS.get(secondary, 0) if secondary else 0)
        + other
    ) * special_cost

    return float(total)


def rate_infantry(data: Dict) -> Dict[str, int]:
    return {'ER': int(calculate_infantry_cost(data) * 1000)}
