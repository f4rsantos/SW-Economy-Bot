import pytest
from utils.currency import parse_currency, split_currency, handle_return


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
