from utils.currency import parse_currency
from services.casino_service import CASINO_RESOURCES, LOCAL_RESOURCES


def parse_casino_wager(amount_str: str) -> list[dict]:
    parsed = parse_currency(amount_str)
    seen = set()
    for entry in parsed:
        resource = entry['resource']
        if resource not in CASINO_RESOURCES:
            raise ValueError(f"'{resource}' cannot be wagered here. Valid resources are ER, CM, EL, CS.")
        if entry['amount'] <= 0:
            raise ValueError(f"Wager amount for {resource} must be greater than zero.")
        if resource in seen:
            raise ValueError(f"You listed {resource} more than once in the same wager.")
        seen.add(resource)
    return parsed


def requires_world(parsed: list[dict]) -> bool:
    return any(entry['resource'] in LOCAL_RESOURCES for entry in parsed)
