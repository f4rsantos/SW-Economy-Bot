# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from typing import Optional
from .errors import FALTypeError, FALSecurityError
from .ast_nodes import (
    Program, AssignStmt, IfStmt, ForEachStmt, RepeatStmt, SwitchStmt,
    TransferAction, BuyBuildingAction, UpgradeBuildingAction,
    MoveFleetAction, FleetStatusAction, RenameFleetAction, BuyVehiclesAction, RecruitAction,
    StopStmt,
    ResourceCond, FleetHealthCond, FleetStatusCond, FleetVehiclesCond, FleetAtWorldCond,
    WorldResourceCond, BuildingCountCond,
    AtWarCond, BlockadedCond, TodayIsCond, FactorySpaceCond, ExprComparison, BinaryCond, NotCond,
    IntLiteral, StrLiteral, VarRef, BinOp, UnaryOp, FleetsAtExpr, RandiExpr, OrdinalExpr, ResourceExpr,
    Expr, Cond, Statement,
)

T_INT = "INT"
T_STR = "STR"
T_LIST = "LIST"
T_UNKNOWN = "UNKNOWN"

RESERVED_NAMES = {"faction_id", "true", "false", "TODAY"}


class TypeCheckResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def check(program: Program) -> TypeCheckResult:
    checker = TypeChecker()
    checker.visit_program(program)
    return checker.result


class TypeChecker:
    def __init__(self):
        self.result = TypeCheckResult()
        self.scope: dict[str, str] = {}


    def visit_program(self, node: Program):
        for stmt in node.body:
            self.visit_statement(stmt)


    def visit_statement(self, node):
        t = type(node)
        if t is AssignStmt:
            self.visit_assign(node)
        elif t is IfStmt:
            self.visit_if(node)
        elif t is ForEachStmt:
            self.visit_for_each(node)
        elif t is RepeatStmt:
            self.visit_repeat(node)
        elif t is SwitchStmt:
            self.visit_switch(node)
        elif t is StopStmt:
            pass
        else:
            self.visit_action(node)

    def visit_assign(self, node: AssignStmt):
        if node.var.lower() in RESERVED_NAMES:
            raise FALSecurityError(
                f"Cannot assign to reserved name '{node.var}'", node.line
            )
        typ = self.infer_expr(node.value)
        self.scope[node.var] = typ

    def visit_if(self, node: IfStmt):
        for branch in node.branches:
            self.check_cond(branch.condition)
            saved = dict(self.scope)
            for stmt in branch.body:
                self.visit_statement(stmt)
            for var, typ in self.scope.items():
                if var not in saved:
                    self.result.warn(
                        f"Variable '{var}' assigned inside IF branch may be unset on other paths"
                    )
            self.scope = saved

        if node.else_body:
            for stmt in node.else_body:
                self.visit_statement(stmt)

    def visit_for_each(self, node: ForEachStmt):
        if node.iterable not in self.scope:
            self.result.error(
                f"Line {node.line}: Variable '{node.iterable}' used before assignment in FOR EACH"
            )
        elif self.scope[node.iterable] != T_LIST:
            self.result.error(
                f"Line {node.line}: FOR EACH requires a list variable, "
                f"but '{node.iterable}' is {self.scope[node.iterable]}"
            )
        self.scope[node.var] = T_INT
        for stmt in node.body:
            self.visit_statement(stmt)

    def visit_repeat(self, node: RepeatStmt):
        for stmt in node.body:
            self.visit_statement(stmt)

    def visit_switch(self, node: SwitchStmt):
        self.infer_expr(node.expr)
        for case in node.cases:
            for stmt in case.body:
                self.visit_statement(stmt)
        for stmt in node.default:
            self.visit_statement(stmt)

    def visit_action(self, node):
        t = type(node)
        if t is TransferAction:
            self._expect_int(node.amount, "TRANSFER amount")
            self._expect_non_list(node.from_world, "TRANSFER FROM world")
            self._expect_non_list(node.to_faction, "TRANSFER TO faction")
            self._expect_non_list(node.to_world, "TRANSFER AT world")
        elif t is BuyBuildingAction:
            self._expect_int(node.amount, "BUY BUILDING amount")
            self._expect_int(node.level, "BUY BUILDING level")
        elif t is UpgradeBuildingAction:
            self._expect_int(node.amount, "UPGRADE BUILDING amount")
            self._expect_int(node.from_level, "UPGRADE FROM LEVEL")
            self._expect_int(node.to_level, "UPGRADE TO LEVEL")
        elif t is MoveFleetAction:
            self._expect_non_list(node.fleet_ref, "MOVE FLEET fleet reference")
            self._expect_non_list(node.destination, "MOVE FLEET destination")
        elif t is FleetStatusAction:
            self._expect_non_list(node.fleet_ref, "FLEET STATUS fleet reference")
        elif t is RenameFleetAction:
            self._expect_non_list(node.fleet_ref, "RENAME FLEET fleet reference")
            self._expect_non_list(node.new_name, "RENAME FLEET new name")
        elif t is BuyVehiclesAction:
            self._expect_int(node.amount, "BUY VEHICLES amount")
        elif t is RecruitAction:
            self._expect_int(node.amount, "RECRUIT MILITARY amount")
            self._expect_int(node.cost, "RECRUIT COST")


    def check_cond(self, node: Cond):
        t = type(node)
        if t is ResourceCond:
            self._expect_int(node.value, f"condition value for {node.resource}")
        elif t is FleetHealthCond:
            self._expect_int(node.value, "FLEET HEALTH condition value")
            self._expect_non_list(node.fleet_ref, "FLEET HEALTH fleet reference")
        elif t is FleetStatusCond:
            self._expect_non_list(node.fleet_ref, "FLEET STATUS fleet reference")
        elif t is FleetVehiclesCond:
            self._expect_int(node.value, "FLEET VEHICLES condition value")
            self._expect_non_list(node.fleet_ref, "FLEET VEHICLES fleet reference")
        elif t is FleetAtWorldCond:
            self._expect_non_list(node.fleet_ref, "FLEET AT WORLD fleet reference")
            self._expect_non_list(node.world_ref, "FLEET AT WORLD world reference")
            if node.faction_ref is not None:
                self._expect_non_list(node.faction_ref, "FLEET AT WORLD faction reference")
        elif t is WorldResourceCond:
            self._expect_int(node.value, f"WORLD resource condition value for {node.resource}")
            self._expect_non_list(node.world_ref, "WORLD resource world reference")
        elif t is BuildingCountCond:
            self._expect_int(node.value, "BUILDINGS condition value")
        elif t is BlockadedCond:
            self._expect_non_list(node.world, "BLOCKADED world reference")
        elif t is FactorySpaceCond:
            self._expect_non_list(node.world, "FACTORY SPACE world reference")
            self._expect_int(node.value, "FACTORY SPACE condition value")
        elif t is ExprComparison:
            self._expect_int(node.left, "left side of comparison")
            self._expect_int(node.right, "right side of comparison")
        elif t is BinaryCond:
            self.check_cond(node.left)
            self.check_cond(node.right)
        elif t is NotCond:
            self.check_cond(node.operand)


    def infer_expr(self, node: Expr) -> str:
        t = type(node)
        if t is IntLiteral:
            return T_INT
        if t is StrLiteral:
            return T_STR
        if t is VarRef:
            if node.name not in self.scope:
                self.result.error(
                    f"Line {node.line}: Variable '{node.name}' used before assignment"
                )
                return T_UNKNOWN
            return self.scope[node.name]
        if t is FleetsAtExpr:
            return T_LIST
        if t is ResourceExpr:
            return T_INT
        if t is RandiExpr:
            self._expect_int(node.low, "RANDI lower bound")
            self._expect_int(node.high, "RANDI upper bound")
            return T_INT
        if t is OrdinalExpr:
            self._expect_int(node.operand, "ORDINAL argument")
            return T_STR
        if t is BinOp:
            lt = self.infer_expr(node.left)
            rt = self.infer_expr(node.right)
            if lt == T_LIST or rt == T_LIST:
                self.result.error(
                    f"Line {node.line}: Cannot use a list in arithmetic"
                )
                return T_UNKNOWN
            if lt == T_STR or rt == T_STR:
                if node.op != "+":
                    self.result.error(
                        f"Line {node.line}: Only '+' (concatenation) is allowed on strings"
                    )
                    return T_UNKNOWN
                return T_STR
            return T_INT
        if t is UnaryOp:
            inner = self.infer_expr(node.operand)
            if inner != T_INT and inner != T_UNKNOWN:
                self.result.error(
                    f"Line {node.line}: Unary minus requires an integer"
                )
            return T_INT
        return T_UNKNOWN


    def _expect_int(self, node: Expr, context: str):
        typ = self.infer_expr(node)
        line = getattr(node, "line", 0)
        if typ not in (T_INT, T_UNKNOWN):
            self.result.error(f"Line {line}: {context} must be an integer, got {typ}")

    def _expect_non_list(self, node: Expr, context: str):
        typ = self.infer_expr(node)
        line = getattr(node, "line", 0)
        if typ == T_LIST:
            self.result.error(f"Line {line}: {context} cannot be a list")
