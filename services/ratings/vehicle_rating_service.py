from typing import Dict, List, Tuple


def parse_engines(engines_str: str) -> List[Tuple[int, str]]:
    if not engines_str or engines_str.strip() == "":
        return []
    result = []
    for part in engines_str.upper().strip().split():
        num_str, size = "", ""
        for char in part:
            if char.isdigit():
                num_str += char
            elif char in ['S', 'M', 'L']:
                size = char
        if num_str and size:
            result.append((int(num_str), size))
    return result


def calculate_er(values: Dict) -> float:
    length = values.get('length', 0)
    main = values.get('main', 0)
    secondary = values.get('secondary', 0)
    lances = values.get('lances', 0)
    pdc = values.get('pdc', 0)
    torpedoes = values.get('torpedoes', 0)
    shield = values.get('shield', False)
    stealth = values.get('stealth', False)
    systems = values.get('systems', 0)
    engines = values.get('engines', [])
    ftl = values.get('ftl', 'NONE')
    cargo = values.get('cargo', 0)
    drone = values.get('drone', False)
    other = values.get('other', 0)
    ftl_modifier = 0 if ftl == "NONE" else 1500
    engine_costs = {'S': 5.5, 'M': 7.5, 'L': 10.5}
    engine_cost = sum(c * engine_costs.get(s, 0) for c, s in engines)
    l_cost = length * (24 + (2 if stealth else 0) + ftl_modifier)
    total = (l_cost + main * 15 + secondary * 10 + lances * 50 + pdc * 5 +
             torpedoes * 5 + (300 if shield else 0) + systems * length +
             engine_cost + other + cargo) * (0.85 if drone else 1)
    return total / 1000


def calculate_cm(values: Dict) -> float:
    length = values.get('length', 0)
    main = values.get('main', 0)
    secondary = values.get('secondary', 0)
    lances = values.get('lances', 0)
    pdc = values.get('pdc', 0)
    torpedoes = values.get('torpedoes', 0)
    shield = values.get('shield', False)
    stealth = values.get('stealth', False)
    systems = values.get('systems', 0)
    engines = values.get('engines', [])
    ftl = values.get('ftl', 'NONE')
    cargo = values.get('cargo', 0)
    drone = values.get('drone', False)
    ftl_modifier = 0 if ftl == "NONE" else (60 if ftl == "INT" else 40)
    engine_costs = {'S': 50, 'M': 70, 'L': 100}
    engine_cost = sum(c * engine_costs.get(s, 0) for c, s in engines)
    l_cost = length * (50 + (20 if stealth else 0) + ftl_modifier)
    total = (l_cost + main * 100 + secondary * 50 + lances * 300 + pdc * 25 +
             torpedoes * 25 + (1000 if shield else 0) + systems * length +
             engine_cost + cargo * 10) * (1.2 if drone else 1)
    return total


def calculate_el(values: Dict) -> float:
    length = values.get('length', 0)
    main = values.get('main', 0)
    secondary = values.get('secondary', 0)
    lances = values.get('lances', 0)
    pdc = values.get('pdc', 0)
    torpedoes = values.get('torpedoes', 0)
    shield = values.get('shield', False)
    stealth = values.get('stealth', False)
    systems = values.get('systems', 0)
    engines = values.get('engines', [])
    ftl = values.get('ftl', 'NONE')
    cargo = values.get('cargo', 0)
    drone = values.get('drone', False)
    ftl_modifier = 0 if ftl == "NONE" else (20 if ftl == "INT" else 10)
    engine_costs = {'S': 50, 'M': 70, 'L': 100}
    engine_cost = sum(c * engine_costs.get(s, 0) for c, s in engines)
    l_cost = length * ((10 if stealth else 0) + ftl_modifier)
    total = (l_cost + main * 100 + secondary * 100 + lances * 200 + pdc * 100 +
             torpedoes * 100 + (1000 if shield else 0) + systems * length * 2 +
             engine_cost + cargo * 5) * (1.5 if drone else 1)
    return total


def calculate_cs(values: Dict) -> int:
    length = values.get('length', 0)
    main = values.get('main', 0)
    secondary = values.get('secondary', 0)
    lances = values.get('lances', 0)
    pdc = values.get('pdc', 0)
    systems = values.get('systems', 0)
    engines = values.get('engines', [])
    ftl = values.get('ftl', 'NONE')
    drone = values.get('drone', False)
    ftl_modifier = 0 if ftl == "NONE" else 10
    engine_costs = {'S': 10, 'M': 20, 'L': 30}
    engine_cost = sum(c * engine_costs.get(s, 0) for c, s in engines)
    total = (length * (5 + ftl_modifier) + main * 10 + secondary * 10 + lances * 20 +
             pdc * 10 + systems * length * 2 + engine_cost) * (0.5 if drone else 1)
    return int(total)


def rate_spacecraft(data: Dict) -> Dict[str, int]:
    if isinstance(data.get('engines'), str):
        data['engines'] = parse_engines(data['engines'])
    m = 0.85 if data.get('boat', False) else 1
    return {
        'ER': int(calculate_er(data) * 1000000000 * m),
        'CM': int(calculate_cm(data) * m),
        'EL': int(calculate_el(data) * m),
        'CS': int(calculate_cs(data) * m)
    }
