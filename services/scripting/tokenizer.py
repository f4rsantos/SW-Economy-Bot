from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List
from .errors import FALSyntaxError

MAX_SCRIPT_LENGTH = 4000


class TT(Enum):
    KW_START = auto()
    KW_ON = auto()
    KW_SET = auto()
    KW_IF = auto()
    KW_ELIF = auto()
    KW_ELSE = auto()
    KW_FOR = auto()
    KW_EACH = auto()
    KW_IN = auto()
    KW_REPEAT = auto()
    KW_TIMES = auto()
    KW_SWITCH = auto()
    KW_CASE = auto()
    KW_DEFAULT = auto()
    KW_TODAY = auto()
    KW_IS = auto()
    KW_NOT = auto()
    KW_AND = auto()
    KW_OR = auto()
    KW_TRANSFER = auto()
    KW_FROM = auto()
    KW_TO = auto()
    KW_AT = auto()
    KW_BUY = auto()
    KW_BUILDING = auto()
    KW_UPGRADE = auto()
    KW_LEVEL = auto()
    KW_MOVE = auto()
    KW_FLEET = auto()
    KW_FLEETS = auto()
    KW_STATUS = auto()
    KW_VEHICLES = auto()
    KW_FACTION = auto()
    KW_WORLD = auto()
    KW_TRIGGER = auto()
    KW_RECRUIT = auto()
    KW_MILITARY = auto()
    KW_COST = auto()
    KW_DURATION = auto()
    KW_NAME = auto()
    KW_HEALTH = auto()
    KW_WAR = auto()
    KW_BLOCKADED = auto()
    KW_BUILDINGS = auto()
    KW_FACTORY = auto()
    KW_SPACE = auto()
    RESOURCE_NAME = auto()
    DAY_NAME = auto()
    STATUS_NAME = auto()
    INT_LITERAL = auto()
    STRING_LITERAL = auto()
    DURATION_LITERAL = auto()
    IDENTIFIER = auto()
    OP_PLUS = auto()
    OP_MINUS = auto()
    OP_STAR = auto()
    OP_SLASH = auto()
    OP_GT = auto()
    OP_GTE = auto()
    OP_LT = auto()
    OP_LTE = auto()
    OP_EQ = auto()
    OP_NEQ = auto()
    OP_ASSIGN = auto()
    COLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


KEYWORDS: dict[str, TT] = {
    "START": TT.KW_START,
    "ON": TT.KW_ON,
    "SET": TT.KW_SET,
    "IF": TT.KW_IF,
    "ELIF": TT.KW_ELIF,
    "ELSE": TT.KW_ELSE,
    "FOR": TT.KW_FOR,
    "EACH": TT.KW_EACH,
    "IN": TT.KW_IN,
    "REPEAT": TT.KW_REPEAT,
    "TIMES": TT.KW_TIMES,
    "SWITCH": TT.KW_SWITCH,
    "CASE": TT.KW_CASE,
    "DEFAULT": TT.KW_DEFAULT,
    "TODAY": TT.KW_TODAY,
    "IS": TT.KW_IS,
    "NOT": TT.KW_NOT,
    "AND": TT.KW_AND,
    "OR": TT.KW_OR,
    "TRANSFER": TT.KW_TRANSFER,
    "FROM": TT.KW_FROM,
    "TO": TT.KW_TO,
    "AT": TT.KW_AT,
    "BUY": TT.KW_BUY,
    "BUILDING": TT.KW_BUILDING,
    "UPGRADE": TT.KW_UPGRADE,
    "LEVEL": TT.KW_LEVEL,
    "MOVE": TT.KW_MOVE,
    "FLEET": TT.KW_FLEET,
    "FLEETS": TT.KW_FLEETS,
    "STATUS": TT.KW_STATUS,
    "VEHICLES": TT.KW_VEHICLES,
    "FACTION": TT.KW_FACTION,
    "WORLD": TT.KW_WORLD,
    "TRIGGER": TT.KW_TRIGGER,
    "RECRUIT": TT.KW_RECRUIT,
    "MILITARY": TT.KW_MILITARY,
    "COST": TT.KW_COST,
    "DURATION": TT.KW_DURATION,
    "NAME": TT.KW_NAME,
    "HEALTH": TT.KW_HEALTH,
    "WAR": TT.KW_WAR,
    "BLOCKADED": TT.KW_BLOCKADED,
    "BUILDINGS": TT.KW_BUILDINGS,
    "FACTORY": TT.KW_FACTORY,
    "SPACE": TT.KW_SPACE,
}

RESOURCE_NAMES = {"CM", "CS", "EL", "U-CM", "U-CS", "U-EL", "ER", "MILITARY", "INFLUENCE", "POPULATION"}

DAY_NAMES = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

STATUS_NAMES = {"IDLE", "MOTHBALLED", "PATROL", "BLOCKADING", "DEFENSE", "PATROL"}

DURATION_SUFFIXES = {"d", "w", "mo"}

try:
    from services.orbital_config import SYSTEMS_DATA as _SYSTEMS_DATA
    _WORLD_NAMES_CANONICAL: dict[str, str] = {
        name.upper(): name
        for system in _SYSTEMS_DATA.values()
        for name in system
        if " " not in name
    }
except Exception:
    _WORLD_NAMES_CANONICAL: dict[str, str] = {}


@dataclass
class Token:
    type: TT
    value: str
    int_value: int
    line: int


def _expand_number(digits: str, suffix: str) -> int:
    if "." in digits:
        base = float(digits)
    else:
        base = int(digits)
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    if suffix:
        return int(base * multipliers[suffix])
    return int(base)


def tokenize(text: str) -> List[Token]:
    if len(text) > MAX_SCRIPT_LENGTH:
        raise FALSyntaxError(f"Script exceeds {MAX_SCRIPT_LENGTH} character limit")

    tokens: List[Token] = []
    lines = text.splitlines()
    indent_stack = [""]
    line_num = 0

    for raw_line in lines:
        line_num += 1

        comment_pos = raw_line.find("#")
        if comment_pos >= 0:
            raw_line = raw_line[:comment_pos]

        if not raw_line.strip():
            continue

        stripped = raw_line.lstrip()
        indent_str = raw_line[: len(raw_line) - len(stripped)]

        current_indent = indent_stack[-1]
        if indent_str == current_indent:
            if tokens and tokens[-1].type not in (TT.NEWLINE, TT.INDENT, TT.DEDENT):
                tokens.append(Token(TT.NEWLINE, "\n", 0, line_num))
        elif len(indent_str) > len(current_indent) and indent_str.startswith(current_indent):
            if tokens and tokens[-1].type not in (TT.COLON,):
                pass
            tokens.append(Token(TT.NEWLINE, "\n", 0, line_num))
            tokens.append(Token(TT.INDENT, indent_str, 0, line_num))
            indent_stack.append(indent_str)
        elif len(indent_str) < len(current_indent):
            tokens.append(Token(TT.NEWLINE, "\n", 0, line_num))
            while indent_stack and indent_stack[-1] != indent_str:
                if not indent_stack:
                    raise FALSyntaxError("Inconsistent indentation", line_num)
                indent_stack.pop()
                tokens.append(Token(TT.DEDENT, "", 0, line_num))
            if not indent_stack or indent_stack[-1] != indent_str:
                raise FALSyntaxError("Inconsistent indentation", line_num)
        else:
            raise FALSyntaxError("Inconsistent indentation", line_num)

        pos = 0
        content = stripped
        while pos < len(content):
            ch = content[pos]

            if ch in " \t":
                pos += 1
                continue

            two = content[pos:pos+2]
            if two == ">=":
                tokens.append(Token(TT.OP_GTE, ">=", 0, line_num))
                pos += 2
                continue
            if two == "<=":
                tokens.append(Token(TT.OP_LTE, "<=", 0, line_num))
                pos += 2
                continue
            if two == "!=":
                tokens.append(Token(TT.OP_NEQ, "!=", 0, line_num))
                pos += 2
                continue
            if two == "==":
                tokens.append(Token(TT.OP_EQ, "==", 0, line_num))
                pos += 2
                continue

            single_map = {
                ">": TT.OP_GT, "<": TT.OP_LT,
                "+": TT.OP_PLUS, "-": TT.OP_MINUS,
                "*": TT.OP_STAR, "/": TT.OP_SLASH,
                "=": TT.OP_ASSIGN,
                ":": TT.COLON,
                "(": TT.LPAREN, ")": TT.RPAREN,
            }
            if ch in single_map:
                tokens.append(Token(single_map[ch], ch, 0, line_num))
                pos += 1
                continue

            if ch == '"':
                pos += 1
                start = pos
                while pos < len(content) and content[pos] != '"':
                    pos += 1
                if pos >= len(content):
                    raise FALSyntaxError("Unterminated string literal", line_num)
                s = content[start:pos]
                tokens.append(Token(TT.STRING_LITERAL, s, 0, line_num))
                pos += 1
                continue

            if ch.isdigit():
                start = pos
                while pos < len(content) and content[pos].isdigit():
                    pos += 1
                if pos < len(content) and content[pos] == ".":
                    pos += 1
                    while pos < len(content) and content[pos].isdigit():
                        pos += 1
                digits = content[start:pos]

                rest = content[pos:]
                dur_suffix = None
                if rest.startswith("mo"):
                    dur_suffix = "mo"
                elif rest and rest[0] in ("d", "w"):
                    dur_suffix = rest[0]

                if dur_suffix:
                    raw = digits + dur_suffix
                    tokens.append(Token(TT.DURATION_LITERAL, raw, 0, line_num))
                    pos += len(dur_suffix)
                    continue

                suffix = ""
                if pos < len(content) and content[pos].upper() in ("K", "M", "B"):
                    suffix = content[pos].upper()
                    pos += 1
                int_val = _expand_number(digits, suffix)
                tokens.append(Token(TT.INT_LITERAL, digits + suffix, int_val, line_num))
                continue

            if ch.isalpha() or ch == "_":
                start = pos
                while pos < len(content) and (content[pos].isalnum() or content[pos] in "_-"):
                    pos += 1
                word = content[start:pos]
                upper = word.upper()


                if upper in RESOURCE_NAMES:
                    tokens.append(Token(TT.RESOURCE_NAME, upper, 0, line_num))
                elif upper in DAY_NAMES:
                    tokens.append(Token(TT.DAY_NAME, upper, 0, line_num))
                elif upper in STATUS_NAMES:
                    tokens.append(Token(TT.STATUS_NAME, upper, 0, line_num))
                elif upper in KEYWORDS:
                    tokens.append(Token(KEYWORDS[upper], upper, 0, line_num))
                elif upper in _WORLD_NAMES_CANONICAL:
                    tokens.append(Token(TT.STRING_LITERAL, _WORLD_NAMES_CANONICAL[upper], 0, line_num))
                else:
                    tokens.append(Token(TT.IDENTIFIER, word, 0, line_num))
                continue

            raise FALSyntaxError(f"Unexpected character '{ch}'", line_num)

    tokens.append(Token(TT.NEWLINE, "\n", 0, line_num))
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TT.DEDENT, "", 0, line_num))

    tokens.append(Token(TT.EOF, "", 0, line_num))
    return tokens
