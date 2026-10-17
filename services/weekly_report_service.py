# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.currency import handle_return

RESOURCE_ORDER = ('ER', 'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS', 'Influence', 'Alloys')
POPULATION = 'Population'
TABLE_RULE = "─"
TABLE_LABELS = {'Influence': 'INF', 'Alloys': 'ALLOY'}


@dataclass(frozen=True, slots=True)
class ResourceFlow:
    name: str
    produced: int
    delta: int
    capped: int
    spent: int
    refunded: int

    @property
    def used(self) -> int:
        return max(self.produced - self.delta, 0) + self.spent

    @property
    def net(self) -> int:
        return self.delta - self.spent - self.capped

    @property
    def ratio(self) -> Optional[float]:
        if self.produced <= 0:
            return None
        return max(self.used, 0) / self.produced

    @property
    def capped_ratio(self) -> Optional[float]:
        if self.produced <= 0:
            return None
        return self.capped / self.produced


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


def build_flows(resources_earned: Dict[str, int], spend_totals,
                resources_produced: Dict[str, int] = None,
                resources_capped: Dict[str, int] = None) -> List[ResourceFlow]:
    produced = resources_earned if resources_produced is None else resources_produced
    capped = resources_capped or {}
    spent = {t.resource_name: int(t.amount) for t in spend_totals}
    refunded = {t.resource_name: int(t.refunded) for t in spend_totals}
    names = (set(resources_earned) | set(produced) | set(spent) | set(capped)) - {POPULATION}
    flows = [
        ResourceFlow(
            name=name,
            produced=int(produced.get(name, 0)),
            delta=int(resources_earned.get(name, 0)),
            capped=int(capped.get(name, 0)),
            spent=spent.get(name, 0),
            refunded=refunded.get(name, 0),
        )
        for name in names
    ]
    flows = [f for f in flows if f.produced or f.delta or f.spent or f.refunded or f.capped]
    return sorted(flows, key=lambda f: _sort_key(f.name))


def _usage_cell(flow: ResourceFlow) -> str:
    ratio = flow.ratio
    if ratio is None:
        return "n/a"
    return f"{ratio * 100:.0f}%"


def build_table(flows: List[ResourceFlow]) -> str:
    show_capped = any(f.capped for f in flows)
    headers = ["RES", "PRODUCED", "USED"] + (["CAPPED"] if show_capped else []) + ["NET", "USAGE"]
    rows = [
        [TABLE_LABELS.get(f.name, f.name), compact_amount(f.produced), compact_amount(f.used)]
        + ([compact_amount(f.capped)] if show_capped else [])
        + [compact_amount(f.net, signed=True), _usage_cell(f)]
        for f in flows
    ]
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))]

    def line(cells) -> str:
        left = cells[0].ljust(widths[0])
        numbers = [cells[i].rjust(widths[i]) for i in range(1, len(cells))]
        return "  ".join([left, *numbers]).rstrip()

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
    total_used = sum(max(f.used, 0) for f in flows)

    if total_used == 0:
        sentences.append("Nothing was consumed this cycle; every unit produced went straight to reserves.")
    elif not deficit:
        sentences.append(f"No resource ran a deficit this cycle; reserves grew in {len(surplus)} of {len(flows)}.")
    else:
        sentences.append(f"The galaxy ran a surplus in {len(surplus)} of {len(flows)} resources.")
        worst = max(deficit, key=lambda f: (f.ratio or float("inf"), -f.net))
        if worst.ratio is None:
            sentences.append(f"{worst.name} was not produced at all, so every unit used came out of stockpiles.")
        else:
            over = (worst.ratio - 1) * 100
            if over > 0:
                sentences.append(f"{worst.name} is the weak point: usage outpaced production by {over:.0f}%, drawing down stockpiles.")
            else:
                sentences.append(f"{worst.name} is the weak point: storage losses pushed reserves down.")

    consuming = [f for f in flows if f.ratio is not None and f.net >= 0 and f.used > 0]
    if consuming:
        top = max(consuming, key=lambda f: f.ratio)
        sentences.append(f"{top.name} saw the heaviest use at {top.ratio * 100:.0f}% of output.")

    capped = [f for f in flows if f.capped > 0 and f.capped_ratio is not None]
    if capped:
        top = max(capped, key=lambda f: f.capped_ratio)
        sentences.append(f"Storage caps destroyed {compact_amount(top.capped)} {top.name}.")

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


def build_weekly_report(resources_earned: Dict[str, int], population_change: int, spend_totals,
                        resources_produced: Dict[str, int] = None,
                        resources_capped: Dict[str, int] = None) -> dict:
    flows = build_flows(resources_earned, spend_totals, resources_produced, resources_capped)
    description = build_headline(flows, population_change)
    if flows:
        description += "\n\n" + build_table(flows)

    fields = [{
        "name": "Population",
        "value": build_population_note(population_change, spend_totals),
        "inline": False,
    }]

    return {"title": "Weekly National Report", "description": description, "fields": fields}
