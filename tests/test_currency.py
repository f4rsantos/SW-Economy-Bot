# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import pytest
from utils.currency import parse_currency, split_currency, handle_return, parse_single_amount


def test_parse_single_amount_inline_resource():
    assert parse_single_amount("10k CM") == (10_000, "CM")


def test_parse_single_amount_uses_fallback_resource():
    assert parse_single_amount("500", fallback_resource="EL") == (500, "EL")


def test_parse_single_amount_inline_beats_fallback():
    assert parse_single_amount("2.5mil CS", fallback_resource="EL") == (2_500_000, "CS")


def test_parse_single_amount_suffixes():
    assert parse_single_amount("10 bil ER") == (10_000_000_000, "ER")
    assert parse_single_amount("5t CS") == (5_000_000_000_000, "CS")


def test_parse_single_amount_rejects_multiple_resources():
    with pytest.raises(ValueError):
        parse_single_amount("10k CM, 5k EL")


def test_parse_single_amount_rejects_unparsable():
    with pytest.raises(ValueError):
        parse_single_amount("abc")


def test_parse_single_amount_requires_a_resource():
    with pytest.raises(ValueError):
        parse_single_amount("500")


def test_parse_single_amount_uppercases_resource():
    assert parse_single_amount("100 cm") == (100, "CM")


def test_parse_currency_simple():
    result = parse_currency("1000 ER")
    assert result == [{"amount": 1000, "resource": "ER"}]


def test_parse_currency_multiple_resources():
    result = parse_currency("500 EL, 300 CM")
    assert result == [
        {"amount": 500, "resource": "EL"},
        {"amount": 300, "resource": "CM"},
    ]


def test_parse_currency_suffix_multipliers():
    result = parse_currency("1.5m CM")
    assert result == [{"amount": 1_500_000, "resource": "CM"}]


def test_parse_currency_billion_trillion_suffix():
    assert parse_currency("1b ER") == [{"amount": 1_000_000_000, "resource": "ER"}]
    assert parse_currency("2t CS") == [{"amount": 2_000_000_000_000, "resource": "CS"}]


def test_handle_return_formats_with_thousands_separator():
    assert handle_return(1000) == "1 000"


def test_handle_return_zero():
    assert handle_return(0) == "0"


def test_handle_return_adds_magnitude_suffix():
    assert "mil" in handle_return(5_000_000)
    assert "bil" in handle_return(5_000_000_000)
