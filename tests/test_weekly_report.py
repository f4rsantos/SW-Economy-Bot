# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from dtos.spend import WeeklySpendTotal
from services.weekly_report_service import (
    build_flows,
    build_headline,
    build_population_note,
    build_table,
    build_weekly_report,
    compact_amount,
)


def test_compact_amount_scales():
    assert compact_amount(0) == "0"
    assert compact_amount(950) == "950"
    assert compact_amount(12_400_000_000) == "12.4 bil"
    assert compact_amount(5_000_000) == "5 mil"
    assert compact_amount(-800_000) == "-800 k"
    assert compact_amount(3_300_000_000, signed=True) == "+3.3 bil"


def test_flows_order_and_population_excluded():
    flows = build_flows(
        {'CM': 10, 'ER': 20, 'Population': 99},
        [WeeklySpendTotal('Population', 5), WeeklySpendTotal('EL', 3)],
    )
    assert [f.name for f in flows] == ['ER', 'CM', 'EL']


def test_table_rows_align():
    flows = build_flows({'ER': 1_000_000, 'CM': 500}, [WeeklySpendTotal('ER', 250_000)])
    table = build_table(flows)
    lines = table.strip("`\n").split("\n")
    assert lines[0].startswith("RES")
    assert "25%" in lines[2]
    assert len({line.index("USAGE") for line in lines[:1]}) == 1


def test_headline_flags_deficit():
    flows = build_flows({'ER': 100, 'CM': 100}, [WeeklySpendTotal('CM', 150)])
    headline = build_headline(flows, 0)
    assert "surplus in 1 of 2" in headline
    assert "CM" in headline and "50%" in headline


def test_headline_no_spending():
    flows = build_flows({'ER': 100}, [])
    assert "Nothing was consumed" in build_headline(flows, 0)


def test_population_note_mentions_recruits():
    note = build_population_note(-20, [WeeklySpendTotal('Population', 5)])
    assert note.startswith("Fell by 20")
    assert "5 recruited" in note


def test_empty_report():
    report = build_weekly_report({}, 0, [])
    assert "No economic activity" in report["description"]
    assert [f["name"] for f in report["fields"]] == ["Population"]


def test_refining_counts_as_use_not_missing_income():
    flows = build_flows(
        {'U-CS': -3_800_000, 'CS': 4_500_000},
        [],
        resources_produced={'U-CS': 2_000_000, 'CS': 5_800_000},
    )
    ucs = next(f for f in flows if f.name == 'U-CS')
    assert ucs.used == 5_800_000
    assert ucs.net == -3_800_000
    assert round(ucs.ratio * 100) == 290
    headline = build_headline(flows, 0)
    assert "not produced" not in headline
    assert "U-CS is the weak point" in headline


def test_capped_column_and_headline():
    flows = build_flows(
        {'CM': 1_000},
        [],
        resources_produced={'CM': 1_000},
        resources_capped={'CM': 250},
    )
    cm = flows[0]
    assert cm.net == 750
    assert cm.capped_ratio == 0.25
    lines = build_table(flows).strip("`\n").split("\n")
    assert lines[0].split() == ["RES", "PRODUCED", "USED", "CAPPED", "NET", "USAGE"]
    assert lines[2].split() == ["CM", "1", "k", "0", "250", "+750", "0%"]
    assert "destroyed 250 CM" in build_headline(flows, 0)


def test_no_capped_column_without_losses():
    flows = build_flows({'CM': 10}, [], resources_produced={'CM': 10})
    assert "CAPPED" not in build_table(flows)
