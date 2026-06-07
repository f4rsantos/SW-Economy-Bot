from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Union
from .errors import FALRuntimeError

MAX_ACTIONS = 200


@dataclass
class FALValue:
    type: Literal["INT", "STR", "LIST"]
    value: Union[int, str, list]

    @staticmethod
    def int(v: int) -> "FALValue":
        return FALValue(type="INT", value=v)

    @staticmethod
    def str_(v: str) -> "FALValue":
        return FALValue(type="STR", value=v)

    @staticmethod
    def list_(v: list) -> "FALValue":
        return FALValue(type="LIST", value=v)


@dataclass
class ExecutionResult:
    actions_taken: int = 0
    skipped: bool = False
    aborted: bool = False
    dry_run: bool = False
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def error(self, msg: str):
        self.errors.append(msg)


class RuntimeContext:
    MAX_ACTIONS = MAX_ACTIONS
    MAX_INT = 10 ** 18
    MAX_FOR_EACH_ITEMS = 40

    def __init__(self, faction_id: int, dry_run: bool = False):
        self.faction_id = faction_id
        self.dry_run = dry_run
        self.variables: dict[str, FALValue] = {}
        self.total_actions: int = 0
        self.result = ExecutionResult(dry_run=dry_run)

    def tick_action(self, description: str):
        self.total_actions += 1
        if self.total_actions > self.MAX_ACTIONS:
            raise FALRuntimeError(
                f"Action limit reached: {self.MAX_ACTIONS} total actions per script run"
            )
        self.result.actions_taken = self.total_actions

    def set_var(self, name: str, value: FALValue):
        self.variables[name] = value

    def get_var(self, name: str) -> FALValue:
        if name not in self.variables:
            raise FALRuntimeError(f"Variable '{name}' is not defined")
        return self.variables[name]

    def safe_int(self, value: int) -> int:
        if abs(value) > self.MAX_INT:
            raise FALRuntimeError("Arithmetic overflow: value exceeds maximum")
        return value
