import re
from typing import List, Tuple, Dict, Any


def handle_currency(input_str: str = "") -> float:
    trim = input_str.strip().lower()
    if trim == "infinity":
        return float('inf')

    letter = trim[-1]
    if letter == 'l':
        letter = trim[-3:]
    if letter == 'ril':
        letter = trim[-4:]

    number_str = trim[:-len(letter)] if letter in ['k', 'm', 'mil', 'b', 'bil', 't', 'tril'] else trim
    try:
        number = float(number_str.replace(',', '.'))
    except ValueError:
        return float('nan')

    multiplier = 1
    if letter in ['t', 'tril']:
        multiplier *= 1000
        letter = 'b'
    if letter in ['b', 'bil']:
        multiplier *= 1000
        letter = 'm'
    if letter in ['m', 'mil']:
        multiplier *= 1000
        letter = 'k'
    if letter == 'k':
        multiplier *= 1000

    return number * multiplier


def split_currency(input_str: str = "", default: str = "ER") -> List[Tuple[float, str]]:
    try:
        trim = input_str.strip()
        pattern = r'(\d+[.,]?\d*)\s*(k|mil?|bil?|tril?|[mbt](?=[^A-Za-z\-]|$))?\s*([A-Za-z][A-Za-z0-9\-]*)?'
        result = []
        for match in re.finditer(pattern, trim, re.IGNORECASE):
            number_str = match.group(1)
            suffix = match.group(2) or ''
            resource = match.group(3).strip().upper() if match.group(3) else ''
            if not number_str:
                continue
            full_number_str = number_str + suffix.lower() if suffix else number_str
            amount = handle_currency(full_number_str)
            if amount != amount:
                continue
            result.append((amount, resource if resource else default))
        return result if result else [(float('nan'), default)]
    except Exception:
        return [(float('nan'), default)]


def resource_array_to_object(arr: List[Tuple[float, str]]) -> Dict[str, float]:
    return {resource: amount for amount, resource in arr}


def handle_return(number: float = 0) -> str:
    if number == 0:
        return "0"
    abs_num = abs(number)
    sign = "-" if number < 0 else ""
    if abs_num >= 1_000_000_000_000:
        suffix = " (tril)"
    elif abs_num >= 1_000_000_000:
        suffix = " (bil)"
    elif abs_num >= 1_000_000:
        suffix = " (mil)"
    else:
        suffix = ""
    return f"{sign}{abs_num:,.0f}".replace(",", " ") + suffix


def handle_return_multiple(obj: Any, order: List[str] = None, join: str = "\n") -> str:
    if isinstance(obj, list):
        obj = resource_array_to_object(obj)
    source = order if order else sorted(obj.keys())
    results = []
    for key in source:
        if obj.get(key, 0) != 0:
            results.append(f"{handle_return(obj[key])} {key}")
    return join.join(results)


def default_resources(resources: List[str]) -> Dict[str, float]:
    return {resource: 0 for resource in resources}


def convert_to_object(resources: List[str], cost_list: List[Tuple[float, str]]) -> Dict[str, float]:
    result = default_resources(resources)
    for amount, name in cost_list:
        if name in result:
            result[name] += amount
    return result


def parse_currency(input_str: str) -> List[Dict[str, Any]]:
    costs = split_currency(input_str)
    result = []
    for amount, resource in costs:
        if not resource or amount != amount:
            raise ValueError("Invalid currency format")
        result.append({'amount': int(amount), 'resource': resource})
    return result
