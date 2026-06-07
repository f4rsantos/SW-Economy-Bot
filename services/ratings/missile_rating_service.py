from typing import Dict
import math

_TYPE_COSTS = {
    'interceptor': {'ER': 4.2,  'CM': 23, 'EL': 19, 'CS': 18},
    'ballistic':   {'ER': 67,   'CM': 89, 'EL': 52, 'CS': 62},
    'ip':          {'ER': 79,   'CM': 87, 'EL': 65, 'CS': 72},
    'gto':         {'ER': 67,   'CM': 45, 'EL': 54, 'CS': 42},
    'cruise':      {'ER': 1.5,  'CM': 45, 'EL': 13, 'CS': 6}
}


def _costs(values: Dict):
    length = values.get('length', 0)
    t = values.get('type', 'cruise')
    nuclear = values.get('nuclear', 0)
    systems = values.get('systems', 0)
    tc = _TYPE_COSTS[t]
    er = math.ceil((length * 1.7 + tc['ER'] + nuclear * 8.6) / 2)
    cm = math.ceil((length * 3.8 + tc['CM'] + nuclear * 16) / 2)
    el = math.ceil((tc['EL'] + nuclear * 8 + 2.5 * tc['EL'] * systems) / 2)
    cs = math.ceil((length * 1.6 + tc['CS'] + nuclear * 3.5) / 2)
    return er, cm, el, cs


def rate_missile(data: Dict) -> Dict[str, int]:
    er, cm, el, cs = _costs(data)
    return {'ER': er * 1000000, 'CM': cm, 'EL': el, 'CS': cs}
