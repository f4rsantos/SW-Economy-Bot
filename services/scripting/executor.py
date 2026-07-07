from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from .errors import FALSyntaxError, FALTypeError, FALSecurityError, FALRuntimeError
from .parser import parse
from .type_checker import check as type_check
from .runtime import RuntimeContext, FALValue, ExecutionResult
from .sandbox import FALSandbox
from .ast_nodes import (
    Program, StartOnDirective,
    AssignStmt, IfStmt, ForEachStmt, RepeatStmt, SwitchStmt,
    TransferAction, BuyBuildingAction, UpgradeBuildingAction,
    MoveFleetAction, FleetStatusAction, BuyVehiclesAction, RecruitAction,
    ResourceCond, FleetHealthCond, FleetStatusCond, FleetVehiclesCond, FleetAtWorldCond,
    WorldResourceCond, BuildingCountCond,
    AtWarCond, BlockadedCond, TodayIsCond, FactorySpaceCond, ExprComparison, BinaryCond, NotCond,
    IntLiteral, StrLiteral, VarRef, BinOp, UnaryOp, FleetsAtExpr, RandiExpr,
)


async def execute_script(
    script_text: str,
    faction_id: int,
    is_company: bool = False,
    dry_run: bool = False,
    current_time: Optional[datetime] = None,
) -> ExecutionResult:
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    ctx = RuntimeContext(faction_id=faction_id, dry_run=dry_run)
    sandbox = FALSandbox(faction_id=faction_id, is_company=is_company, dry_run=dry_run, current_time=current_time)

    try:
        ast = parse(script_text)
    except FALSyntaxError as e:
        ctx.result.error(str(e))
        ctx.result.aborted = True
        return ctx.result

    tc_result = type_check(ast)
    for err in tc_result.errors:
        ctx.result.error(err)
    for warn in tc_result.warnings:
        ctx.result.warn(warn)
    if not tc_result.ok:
        ctx.result.aborted = True
        return ctx.result

    execution_day = await sandbox.get_current_day_name()
    if ast.directives:
        directive: StartOnDirective = ast.directives[0]
        if directive.day == "TRIGGER":
            ctx.result.skipped = True
            return ctx.result
        if directive.day != execution_day:
            ctx.result.skipped = True
            return ctx.result

    executor = Executor(ctx=ctx, sandbox=sandbox, current_time=current_time)
    await executor.run_statements(ast.body)
    return ctx.result


async def execute_script_manual(
    script_text: str,
    faction_id: int,
    is_company: bool = False,
    dry_run: bool = False,
    current_time: Optional[datetime] = None,
) -> ExecutionResult:
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    ctx = RuntimeContext(faction_id=faction_id, dry_run=dry_run)
    sandbox = FALSandbox(faction_id=faction_id, is_company=is_company, dry_run=dry_run, current_time=current_time)

    try:
        ast = parse(script_text)
    except FALSyntaxError as e:
        ctx.result.error(str(e))
        ctx.result.aborted = True
        return ctx.result

    tc_result = type_check(ast)
    for err in tc_result.errors:
        ctx.result.error(err)
    for warn in tc_result.warnings:
        ctx.result.warn(warn)
    if not tc_result.ok:
        ctx.result.aborted = True
        return ctx.result

    executor = Executor(ctx=ctx, sandbox=sandbox, current_time=current_time)
    await executor.run_statements(ast.body)
    return ctx.result


class Executor:
    def __init__(self, ctx: RuntimeContext, sandbox: FALSandbox, current_time: datetime):
        self.ctx = ctx
        self.sandbox = sandbox
        self.current_time = current_time


    async def run_statements(self, stmts: list):
        for stmt in stmts:
            if self.ctx.result.aborted:
                break
            await self.run_statement(stmt)

    async def run_statement(self, stmt):
        t = type(stmt)
        try:
            if t is AssignStmt:
                await self.exec_assign(stmt)
            elif t is IfStmt:
                await self.exec_if(stmt)
            elif t is ForEachStmt:
                await self.exec_for_each(stmt)
            elif t is RepeatStmt:
                await self.exec_repeat(stmt)
            elif t is SwitchStmt:
                await self.exec_switch(stmt)
            else:
                await self.exec_action(stmt)
        except FALRuntimeError as e:
            self.ctx.result.error(str(e))
            self.ctx.result.aborted = True
        except FALSecurityError as e:
            self.ctx.result.error(f"Security violation: {e}")
            self.ctx.result.aborted = True
        except ValueError as e:
            line = getattr(stmt, "line", 0)
            self.ctx.result.error(f"Line {line}: {e}")


    async def exec_assign(self, stmt: AssignStmt):
        value = await self.eval_expr(stmt.value)
        self.ctx.set_var(stmt.var, value)

    async def exec_if(self, stmt: IfStmt):
        for branch in stmt.branches:
            cond_val = await self.eval_cond(branch.condition)
            if cond_val:
                await self.run_statements(branch.body)
                return
        if stmt.else_body:
            await self.run_statements(stmt.else_body)

    async def exec_for_each(self, stmt: ForEachStmt):
        list_val = self.ctx.get_var(stmt.iterable)
        if list_val.type != "LIST":
            raise FALRuntimeError(f"FOR EACH requires a list variable, '{stmt.iterable}' is {list_val.type}")
        items = list_val.value
        if len(items) > self.ctx.MAX_FOR_EACH_ITEMS:
            items = items[:self.ctx.MAX_FOR_EACH_ITEMS]
            self.ctx.result.warn(f"FOR EACH list truncated to {self.ctx.MAX_FOR_EACH_ITEMS} items")
        for item in items:
            if self.ctx.result.aborted:
                break
            self.ctx.set_var(stmt.var, FALValue.int(item))
            await self.run_statements(stmt.body)

    async def exec_repeat(self, stmt: RepeatStmt):
        for _ in range(stmt.count):
            if self.ctx.result.aborted:
                break
            await self.run_statements(stmt.body)

    async def exec_switch(self, stmt: SwitchStmt):
        value = await self.eval_expr(stmt.expr)
        for case in stmt.cases:
            case_val = await self.eval_expr(case.value)
            if value.value == case_val.value:
                await self.run_statements(case.body)
                return
        if stmt.default:
            await self.run_statements(stmt.default)


    async def exec_action(self, stmt):
        self.ctx.tick_action(repr(stmt))
        t = type(stmt)
        if t is TransferAction:
            await self.exec_transfer(stmt)
        elif t is BuyBuildingAction:
            await self.exec_buy_building(stmt)
        elif t is UpgradeBuildingAction:
            await self.exec_upgrade_building(stmt)
        elif t is MoveFleetAction:
            await self.exec_move_fleet(stmt)
        elif t is FleetStatusAction:
            await self.exec_fleet_status(stmt)
        elif t is BuyVehiclesAction:
            await self.exec_buy_vehicles(stmt)
        elif t is RecruitAction:
            await self.exec_recruit(stmt)
        else:
            raise FALRuntimeError(f"Unknown action type: {type(stmt).__name__}")

    async def exec_transfer(self, stmt: TransferAction):
        amount = (await self.eval_expr(stmt.amount)).value
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"TRANSFER amount must be a positive integer, got {amount}")
        amount = self.ctx.safe_int(amount)

        from_world_ref = (await self.eval_expr(stmt.from_world)).value
        to_faction_ref = (await self.eval_expr(stmt.to_faction)).value
        to_world_ref = (await self.eval_expr(stmt.to_world)).value

        from_world = await self.sandbox.resolve_world(from_world_ref)
        to_world = await self.sandbox.resolve_world(to_world_ref)
        to_faction = await self.sandbox.resolve_faction(str(to_faction_ref))

        msg = await self.sandbox.do_transfer(
            amount=amount,
            resource_name=stmt.resource,
            from_world_id=from_world["id"],
            from_world_name=from_world["name"],
            to_faction_id=to_faction["id"],
            to_world_id=to_world["id"],
            to_world_name=to_world["name"],
            current_time=self.current_time,
        )


    async def exec_buy_building(self, stmt: BuyBuildingAction):
        building_ref_val = (await self.eval_expr(stmt.building_ref)).value
        amount = (await self.eval_expr(stmt.amount)).value
        world_ref_val = (await self.eval_expr(stmt.world)).value
        level = (await self.eval_expr(stmt.level)).value

        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"BUY BUILDING amount must be positive, got {amount}")
        if not isinstance(level, int) or level <= 0:
            raise ValueError(f"BUY BUILDING level must be positive, got {level}")

        building = await self.sandbox.resolve_building(building_ref_val)
        world = await self.sandbox.resolve_world(world_ref_val)

        msg = await self.sandbox.do_buy_building(
            building_id=building["id"], amount=amount,
            world_id=world["id"], level=level,
        )


    async def exec_upgrade_building(self, stmt: UpgradeBuildingAction):
        building_ref_val = (await self.eval_expr(stmt.building_ref)).value
        amount = (await self.eval_expr(stmt.amount)).value
        world_ref_val = (await self.eval_expr(stmt.world)).value
        from_level = (await self.eval_expr(stmt.from_level)).value
        to_level = (await self.eval_expr(stmt.to_level)).value

        building = await self.sandbox.resolve_building(building_ref_val)
        world = await self.sandbox.resolve_world(world_ref_val)

        msg = await self.sandbox.do_upgrade_building(
            building_id=building["id"], amount=amount,
            world_id=world["id"], from_level=from_level, to_level=to_level,
        )


    async def exec_move_fleet(self, stmt: MoveFleetAction):
        fleet_ref_val = (await self.eval_expr(stmt.fleet_ref)).value
        dest_ref_val = (await self.eval_expr(stmt.destination)).value

        fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
        dest_world = await self.sandbox.resolve_world(dest_ref_val)

        msg = await self.sandbox.do_move_fleet(
            fleet_id=fleet["id"],
            fleet_world_name=fleet["world_name"],
            dest_world_id=dest_world["id"],
            dest_world_name=dest_world["name"],
            current_time=self.current_time,
        )


    async def exec_fleet_status(self, stmt: FleetStatusAction):
        fleet_ref_val = (await self.eval_expr(stmt.fleet_ref)).value
        fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
        msg = await self.sandbox.do_fleet_status(fleet_id=fleet["id"], status_name=stmt.status)


    async def exec_buy_vehicles(self, stmt: BuyVehiclesAction):
        vehicle_ref_val = (await self.eval_expr(stmt.vehicle_ref)).value
        fleet_ref_val = (await self.eval_expr(stmt.fleet_ref)).value
        amount = (await self.eval_expr(stmt.amount)).value

        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"BUY VEHICLES amount must be positive, got {amount}")

        vehicle = await self.sandbox.resolve_vehicle(vehicle_ref_val)
        fleet = await self.sandbox.resolve_fleet(fleet_ref_val)

        msg = await self.sandbox.do_buy_vehicles(
            vehicle_id=vehicle["id"], fleet_id=fleet["id"],
            amount=amount, current_time=self.current_time,
        )


    async def exec_recruit(self, stmt: RecruitAction):
        amount = (await self.eval_expr(stmt.amount)).value
        cost = (await self.eval_expr(stmt.cost)).value
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"RECRUIT amount must be positive, got {amount}")
        if not isinstance(cost, int) or cost < 0:
            raise ValueError(f"RECRUIT COST must be non-negative, got {cost}")
        msg = await self.sandbox.do_recruit(
            amount=amount, cost_per_unit=cost,
            resource_name=stmt.resource, duration=stmt.duration, name=stmt.name,
        )



    async def eval_cond(self, cond) -> bool:
        t = type(cond)

        if t is ResourceCond:
            current = await self.sandbox.get_resource_amount(cond.resource)
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(current, cond.op, threshold)

        if t is FleetHealthCond:
            fleet_ref_val = (await self.eval_expr(cond.fleet_ref)).value
            fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
            health = await self.sandbox.get_fleet_health(fleet["id"])
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(health, cond.op, threshold)

        if t is FleetStatusCond:
            fleet_ref_val = (await self.eval_expr(cond.fleet_ref)).value
            fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
            status = await self.sandbox.get_fleet_status_name(fleet["id"])
            return status == cond.status.upper()

        if t is FleetVehiclesCond:
            fleet_ref_val = (await self.eval_expr(cond.fleet_ref)).value
            fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
            count = await self.sandbox.get_fleet_vehicle_count(fleet["id"])
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(count, cond.op, threshold)

        if t is FleetAtWorldCond:
            fleet_ref_val = (await self.eval_expr(cond.fleet_ref)).value
            world_ref_val = (await self.eval_expr(cond.world_ref)).value
            world = await self.sandbox.resolve_world(world_ref_val)
            if cond.faction_ref is not None:
                faction_ref_val = (await self.eval_expr(cond.faction_ref)).value
                faction = await self.sandbox.resolve_faction(str(faction_ref_val))
                faction_id = faction["id"]
                fleet = await self.sandbox.resolve_fleet_for_faction(fleet_ref_val, faction_id)
                fleet_ids = await self.sandbox.get_fleets_at_world_for_faction(world["id"], faction_id)
            else:
                fleet = await self.sandbox.resolve_fleet(fleet_ref_val)
                fleet_ids = await self.sandbox.get_fleets_at_world(world["id"])
            return fleet["id"] in fleet_ids

        if t is WorldResourceCond:
            world_ref_val = (await self.eval_expr(cond.world_ref)).value
            world = await self.sandbox.resolve_world(world_ref_val)
            amount = await self.sandbox.get_world_resource_amount(world["id"], cond.resource)
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(amount, cond.op, threshold)

        if t is BuildingCountCond:
            building_ref_val = (await self.eval_expr(cond.building_ref)).value
            world_ref_val = (await self.eval_expr(cond.world)).value
            building = await self.sandbox.resolve_building(building_ref_val)
            world = await self.sandbox.resolve_world(world_ref_val)
            count = await self.sandbox.get_building_count(building["id"], world["id"])
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(count, cond.op, threshold)

        if t is AtWarCond:
            return await self.sandbox.is_at_war()

        if t is BlockadedCond:
            world_ref_val = (await self.eval_expr(cond.world)).value
            world = await self.sandbox.resolve_world(world_ref_val)
            return await self.sandbox.is_blockaded(world["id"])

        if t is TodayIsCond:
            today = await self.sandbox.get_current_day_name()
            return today == cond.day

        if t is FactorySpaceCond:
            world_ref_val = (await self.eval_expr(cond.world)).value
            world = await self.sandbox.resolve_world(world_ref_val)
            available = await self.sandbox.get_factory_space_available(world["id"])
            threshold = (await self.eval_expr(cond.value)).value
            return self._compare(available, cond.op, threshold)

        if t is ExprComparison:
            left = (await self.eval_expr(cond.left)).value
            right = (await self.eval_expr(cond.right)).value
            return self._compare(left, cond.op, right)

        if t is BinaryCond:
            if cond.op == "AND":
                return await self.eval_cond(cond.left) and await self.eval_cond(cond.right)
            if cond.op == "OR":
                return await self.eval_cond(cond.left) or await self.eval_cond(cond.right)

        if t is NotCond:
            return not await self.eval_cond(cond.operand)

        raise FALRuntimeError(f"Unknown condition type: {type(cond).__name__}")

    def _compare(self, left, op: str, right) -> bool:
        if op == ">":  return left > right
        if op == ">=": return left >= right
        if op == "<":  return left < right
        if op == "<=": return left <= right
        if op == "==": return left == right
        if op == "!=": return left != right
        raise FALRuntimeError(f"Unknown operator '{op}'")


    async def eval_expr(self, node) -> FALValue:
        t = type(node)

        if t is IntLiteral:
            return FALValue.int(node.value)

        if t is StrLiteral:
            return FALValue.str_(node.value)

        if t is VarRef:
            return self.ctx.get_var(node.name)

        if t is FleetsAtExpr:
            world_ref_val = (await self.eval_expr(node.world)).value
            world = await self.sandbox.resolve_world(world_ref_val)
            fleet_ids = await self.sandbox.get_fleets_at_world(world["id"])
            return FALValue.list_(fleet_ids)

        if t is BinOp:
            left = (await self.eval_expr(node.left)).value
            right = (await self.eval_expr(node.right)).value
            if not isinstance(left, int) or not isinstance(right, int):
                raise FALRuntimeError(
                    f"Line {node.line}: Arithmetic requires integers, got {type(left).__name__} and {type(right).__name__}"
                )
            if node.op == "+":
                result = left + right
            elif node.op == "-":
                result = left - right
            elif node.op == "*":
                result = left * right
            elif node.op == "/":
                if right == 0:
                    raise FALRuntimeError(f"Line {node.line}: Division by zero")
                result = left // right
            else:
                raise FALRuntimeError(f"Unknown operator '{node.op}'")
            return FALValue.int(self.ctx.safe_int(result))

        if t is RandiExpr:
            low = (await self.eval_expr(node.low)).value
            high = (await self.eval_expr(node.high)).value
            if not isinstance(low, int) or not isinstance(high, int):
                raise FALRuntimeError(f"Line {node.line}: RANDI requires integer bounds")
            if low > high:
                raise FALRuntimeError(f"Line {node.line}: RANDI lower bound {low} exceeds upper bound {high}")
            return FALValue.int(self.ctx.rng.randint(low, high))

        if t is UnaryOp:
            val = (await self.eval_expr(node.operand)).value
            if not isinstance(val, int):
                raise FALRuntimeError(f"Unary minus requires an integer")
            return FALValue.int(-val)

        raise FALRuntimeError(f"Unknown expression type: {type(node).__name__}")



async def run_income_day_scripts(
    factions: list,
    income_weekday_name: str,
    current_time: datetime,
) -> None:
    from .script_service import get_scripts_for_income_day, record_execution
    import time

    scripts = await get_scripts_for_income_day(income_weekday_name)
    if not scripts:
        return

    logger.info(f"  Running {len(scripts)} faction script(s) for income day ({income_weekday_name})")

    faction_is_company = {f["id"]: f.get("is_company", False) for f in factions}

    for script_row in scripts:
        start = time.monotonic()
        try:
            import asyncio
            result = await asyncio.wait_for(
                execute_script(
                    script_text=script_row["script_text"],
                    faction_id=script_row["faction_id"],
                    is_company=faction_is_company.get(script_row["faction_id"], False),
                    dry_run=False,
                    current_time=current_time,
                ),
                timeout=30.0,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            from .runtime import ExecutionResult
            result = ExecutionResult()
            result.error(f"Unexpected error: {e}")
            result.aborted = True
            await record_execution(script_row["id"], script_row["faction_id"], result, elapsed)
            logger.error(f"    Script {script_row['id']} (faction {script_row['faction_id']}): ERROR — {e}")
            continue

        elapsed = int((time.monotonic() - start) * 1000)
        await record_execution(script_row["id"], script_row["faction_id"], result, elapsed)

        status = "skipped" if result.skipped else ("aborted" if result.aborted else "ok")
        logger.info(f"    Script {script_row['id']} (faction {script_row['faction_id']}): {status}, {result.actions_taken} actions, {elapsed}ms")


async def run_scheduled_scripts(current_time: datetime) -> None:
    from .script_service import get_scripts_for_scheduled_day, record_execution
    import time

    days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    today = days[current_time.weekday()]

    scripts = await get_scripts_for_scheduled_day(today, current_time)
    if not scripts:
        return

    logger.info(f"  Running {len(scripts)} scheduled script(s) for {today}")

    for script_row in scripts:
        start = time.monotonic()
        try:
            import asyncio
            result = await asyncio.wait_for(
                execute_script(
                    script_text=script_row["script_text"],
                    faction_id=script_row["faction_id"],
                    is_company=script_row.get("is_company", False),
                    dry_run=False,
                    current_time=current_time,
                ),
                timeout=30.0,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            from .runtime import ExecutionResult
            result = ExecutionResult()
            result.error(f"Unexpected error: {e}")
            result.aborted = True
            await record_execution(script_row["id"], script_row["faction_id"], result, elapsed)
            continue

        elapsed = int((time.monotonic() - start) * 1000)
        await record_execution(script_row["id"], script_row["faction_id"], result, elapsed)
