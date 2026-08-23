# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union



@dataclass
class IntLiteral:
    value: int
    line: int = 0


@dataclass
class StrLiteral:
    value: str
    line: int = 0


@dataclass
class VarRef:
    name: str
    line: int = 0


@dataclass
class BinOp:
    left: "Expr"
    op: str
    right: "Expr"
    line: int = 0


@dataclass
class UnaryOp:
    op: str
    operand: "Expr"
    line: int = 0


@dataclass
class FleetsAtExpr:
    world: "Expr"
    line: int = 0


@dataclass
class RandiExpr:
    low: "Expr"
    high: "Expr"
    line: int = 0


@dataclass
class OrdinalExpr:
    operand: "Expr"
    line: int = 0


Expr = Union[IntLiteral, StrLiteral, VarRef, BinOp, UnaryOp, FleetsAtExpr, RandiExpr, OrdinalExpr]
Literal = Union[IntLiteral, StrLiteral]



@dataclass
class ResourceCond:
    resource: str
    op: str
    value: Expr
    line: int = 0


@dataclass
class FleetHealthCond:
    fleet_ref: Expr
    op: str
    value: Expr
    line: int = 0


@dataclass
class FleetStatusCond:
    fleet_ref: Expr
    status: str
    line: int = 0


@dataclass
class FleetVehiclesCond:
    fleet_ref: Expr
    op: str
    value: Expr
    line: int = 0


@dataclass
class FleetAtWorldCond:
    fleet_ref: Expr
    faction_ref: Optional[Expr]
    world_ref: Expr
    line: int = 0


@dataclass
class WorldResourceCond:
    resource: str
    world_ref: Expr
    op: str
    value: Expr
    line: int = 0


@dataclass
class BuildingCountCond:
    building_ref: Expr
    world: Expr
    op: str
    value: Expr
    line: int = 0


@dataclass
class AtWarCond:
    line: int = 0


@dataclass
class BlockadedCond:
    world: Expr
    line: int = 0


@dataclass
class TodayIsCond:
    day: str
    line: int = 0


@dataclass
class FactorySpaceCond:
    world: "Expr"
    op: str
    value: "Expr"
    line: int = 0


@dataclass
class ExprComparison:
    left: Expr
    op: str
    right: Expr
    line: int = 0


@dataclass
class BinaryCond:
    left: "Cond"
    op: str
    right: "Cond"
    line: int = 0


@dataclass
class NotCond:
    operand: "Cond"
    line: int = 0


Cond = Union[
    ResourceCond, FleetHealthCond, FleetStatusCond, FleetVehiclesCond, FleetAtWorldCond,
    WorldResourceCond, BuildingCountCond,
    AtWarCond, BlockadedCond, TodayIsCond, FactorySpaceCond, ExprComparison, BinaryCond, NotCond,
]



@dataclass
class TransferAction:
    amount: Expr
    resource: str
    from_world: Expr
    to_faction: Expr
    to_world: Expr
    line: int = 0


@dataclass
class BuyBuildingAction:
    building_ref: Expr
    amount: Expr
    world: Expr
    level: Expr
    line: int = 0


@dataclass
class UpgradeBuildingAction:
    building_ref: Expr
    amount: Expr
    world: Expr
    from_level: Expr
    to_level: Expr
    line: int = 0


@dataclass
class MoveFleetAction:
    fleet_ref: Expr
    destination: Expr
    line: int = 0


@dataclass
class FleetStatusAction:
    fleet_ref: Expr
    status: str
    line: int = 0


@dataclass
class RenameFleetAction:
    fleet_ref: Expr
    new_name: Expr
    line: int = 0


@dataclass
class BuyVehiclesAction:
    vehicle_ref: Expr
    fleet_ref: Expr
    amount: Expr
    line: int = 0


@dataclass
class RecruitAction:
    amount: Expr
    cost: Expr
    resource: str
    duration: str
    name: str
    line: int = 0


Action = Union[
    TransferAction, BuyBuildingAction, UpgradeBuildingAction,
    MoveFleetAction, FleetStatusAction, RenameFleetAction, BuyVehiclesAction, RecruitAction,
]



@dataclass
class AssignStmt:
    var: str
    value: Expr
    line: int = 0


@dataclass
class IfBranch:
    condition: Cond
    body: list


@dataclass
class IfStmt:
    branches: list
    else_body: list
    line: int = 0


@dataclass
class ForEachStmt:
    var: str
    iterable: str
    body: list
    line: int = 0


@dataclass
class RepeatStmt:
    count: int
    body: list
    line: int = 0


@dataclass
class SwitchCase:
    value: Literal
    body: list


@dataclass
class SwitchStmt:
    expr: Expr
    cases: list
    default: list
    line: int = 0


Statement = Union[
    AssignStmt, IfStmt, ForEachStmt, RepeatStmt, SwitchStmt, Action,
]



@dataclass
class StartOnDirective:
    day: str
    line: int = 0


@dataclass
class Program:
    directives: list
    body: list
