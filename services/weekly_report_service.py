# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.currency import handle_return
from utils.embeds import BAR_FILLED, BAR_EMPTY

RESOURCE_ORDER = ('ER', 'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS', 'Influence', 'Alloys')
POPULATION = 'Population'
BAR_WIDTH = 8
TABLE_RULE = "─"
TABLE_LABELS = {'Influence': 'INF', 'Alloys': 'ALLOY'}


@dataclass(frozen=True, slots=True)
class ResourceFlow:
    name: str
    earned: int
    spent: int
    refunded: int

    @property
    def net(self) -> int:
        return self.earned - self.spent

    @property
    def ratio(self) -> Optional[float]:
        if self.earned <= 0:
            return None
        return max(self.spent, 0) / self.earned


def compact_amount(value: int, signed: bool = False) -> str:
    sign = ""
    if value < 0:
        sign = "-"
    elif signed and value > 0:
        sign = "+"
    magnitude = abs(value)
    for threshold, suffix in ((1_000_000_000_000, "tril"), (1_000_000_000, "bil"), (1_000_000, "mil"), (1_000, "k")):
        if magnitude >= threshold:
            scaled = magnitude / threshold
            text = f"{scaled:.1f}".rstrip("0").rstrip(".") if scaled < 100 else f"{scaled:.0f}"
            return f"{sign}{text} {suffix}"
    return f"{sign}{magnitude:,.0f}".replace(",", " ")


def _sort_key(name: str):
    if name in RESOURCE_ORDER:
        return (0, RESOURCE_ORDER.index(name), name)
    return (1, 0, name)


def build_flows(resources_earned: Dict[str, int], spend_totals) -> List[ResourceFlow]:
    spent = {t.resource_name: int(t.amount) for t in spend_totals}
    refunded = {t.resource_name: int(t.refunded) for t in spend_totals}
    names = (set(resources_earned) | set(spent)) - {POPULATION}
    flows = [
        ResourceFlow(
            name=name,
            earned=int(resources_earned.get(name, 0)),
            spent=spent.get(name, 0),
            refunded=refunded.get(name, 0),
        )
        for name in names
    ]
    flows = [f for f in flows if f.earned or f.spent or f.refunded]
    return sorted(flows, key=lambda f: _sort_key(f.name))


def _usage_cell(flow: ResourceFlow) -> str:
    ratio = flow.ratio
    if ratio is None:
        return BAR_EMPTY * BAR_WIDTH + "   n/a"
    filled = int(round(min(ratio, 1.0) * BAR_WIDTH))
    return BAR_FILLED * filled + BAR_EMPTY * (BAR_WIDTH - filled) + f" {ratio * 100:>4.0f}%"


def build_table(flows: List[ResourceFlow]) -> str:
    headers = ("RES", "EARNED", "SPENT", "NET", "REINVESTED")
    rows = [
        (
            TABLE_LABELS.get(f.name, f.name),
            compact_amount(f.earned),
            compact_amount(f.spent),
            compact_amount(f.net, signed=True),
            _usage_cell(f),
        )
        for f in flows
    ]
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(4)]

    def line(cells) -> str:
        left = cells[0].ljust(widths[0])
        numbers = [cells[i].rjust(widths[i]) for i in range(1, 4)]
        return "  ".join([left, *numbers, cells[4]]).rstrip()

    header = line(headers)
    body = [line(r) for r in rows]
    rule = TABLE_RULE * max(len(header), *(len(b) for b in body))
    return "```\n" + "\n".join([header, rule, *body]) + "\n```"


def build_headline(flows: List[ResourceFlow], population_change: int) -> str:
    if not flows:
        return "No economic activity was recorded this cycle."

    sentences = []
    surplus = [f for f in flows if f.net > 0]
    deficit = [f for f in flows if f.net < 0]
    total_spent = sum(max(f.spent, 0) for f in flows)

    if total_spent == 0:
        sentences.append("No spending was recorded this cycle; every unit of income went straight to reserves.")
    elif not deficit:
        sentences.append(f"No resource ran a deficit this cycle; reserves grew in {len(surplus)} of {len(flows)}.")
    else:
        sentences.append(f"The galaxy ran a surplus in {len(surplus)} of {len(flows)} resources.")
        worst = max(deficit, key=lambda f: (f.ratio or float("inf"), -f.net))
        if worst.ratio is None:
            sentences.append(f"{worst.name} had no income at all, so every unit spent came out of stockpiles.")
        else:
            over = (worst.ratio - 1) * 100
            sentences.append(f"{worst.name} is the weak point: spending outpaced income by {over:.0f}%, drawing down stockpiles.")

    reinvesting = [f for f in flows if f.ratio is not None and f.net >= 0 and f.spent > 0]
    if reinvesting:
        top = max(reinvesting, key=lambda f: f.ratio)
        sentences.append(f"{top.name} saw the heaviest reinvestment at {top.ratio * 100:.0f}% of income.")

    if population_change > 0:
        sentences.append(f"Population grew by {handle_return(population_change)}.")
    elif population_change < 0:
        sentences.append(f"Population fell by {handle_return(-population_change)}.")

    return " ".join(sentences)


def build_population_note(population_change: int, spend_totals) -> str:
    if population_change > 0:
        text = f"Grew by {handle_return(population_change)} across the galaxy."
    elif population_change < 0:
        text = f"Fell by {handle_return(-population_change)} across the galaxy."
    else:
        text = "Held steady across the galaxy."
    recruited = sum(int(t.amount) for t in spend_totals if t.resource_name == POPULATION)
    if recruited > 0:
        text += f"\n{handle_return(recruited)} recruited into units."
    return text


def build_weekly_report(resources_earned: Dict[str, int], population_change: int, spend_totals) -> dict:
    flows = build_flows(resources_earned, spend_totals)
    description = build_headline(flows, population_change)
    if flows:
        description += "\n\n" + build_table(flows)

    fields = [{
        "name": "Population",
        "value": build_population_note(population_change, spend_totals),
        "inline": False,
    }]

    return {"title": "Weekly National Report", "description": description, "fields": fields}
