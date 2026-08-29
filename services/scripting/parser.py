# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from __future__ import annotations
from typing import List, Optional
from .errors import FALSyntaxError
from .tokenizer import Token, TT, tokenize
from .ast_nodes import (
    Program, StartOnDirective,
    AssignStmt, IfStmt, IfBranch, ForEachStmt, RepeatStmt, SwitchStmt, SwitchCase,
    TransferAction, BuyBuildingAction, UpgradeBuildingAction,
    MoveFleetAction, FleetStatusAction, RenameFleetAction, BuyVehiclesAction, RecruitAction,
    StopStmt,
    ResourceCond, FleetHealthCond, FleetStatusCond, FleetAtWorldCond, FleetVehiclesCond,
    BuildingCountCond, WorldResourceCond,
    AtWarCond, BlockadedCond, TodayIsCond, FactorySpaceCond, ExprComparison, BinaryCond, NotCond,
    IntLiteral, StrLiteral, VarRef, BinOp, UnaryOp, FleetsAtExpr, RandiExpr, OrdinalExpr, ResourceExpr,
    Expr, Cond, Statement, Literal,
)

MAX_STATEMENTS = 100
MAX_REPEAT = 40


def parse(text: str) -> Program:
    tokens = tokenize(text)
    p = Parser(tokens)
    return p.parse_program()


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self._stmt_count = 0


    def peek(self, offset: int = 0) -> Token:
        i = self.pos + offset
        if i >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[i]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def check(self, *types: TT) -> bool:
        return self.peek().type in types

    def match(self, *types: TT) -> Optional[Token]:
        if self.check(*types):
            return self.advance()
        return None

    def expect(self, *types: TT, msg: str = "") -> Token:
        tok = self.peek()
        if tok.type not in types:
            names = "/".join(t.name for t in types)
            desc = msg or f"expected {names}"
            raise FALSyntaxError(f"{desc}, got '{tok.value or tok.type.name}'", tok.line)
        return self.advance()

    def skip_newlines(self):
        while self.check(TT.NEWLINE):
            self.advance()

    def current_line(self) -> int:
        return self.peek().line


    def parse_program(self) -> Program:
        self.skip_newlines()
        directives = []
        body = []

        while not self.check(TT.EOF):
            self.skip_newlines()
            if self.check(TT.EOF):
                break
            if self.check(TT.KW_START):
                directives.append(self.parse_directive())
            else:
                stmt = self.parse_statement()
                if stmt is not None:
                    body.append(stmt)
            self.skip_newlines()

        if len(directives) > 1:
            raise FALSyntaxError("Only one START ON directive is allowed", directives[1].line)

        return Program(directives=directives, body=body)

    def parse_directive(self) -> StartOnDirective:
        tok = self.expect(TT.KW_START)
        self.expect(TT.KW_ON, msg="expected ON after START")
        if self.check(TT.KW_TRIGGER):
            self.advance()
            return StartOnDirective(day="TRIGGER", line=tok.line)
        day_tok = self.expect(TT.DAY_NAME, msg="expected day name or TRIGGER after START ON")
        return StartOnDirective(day=day_tok.value, line=tok.line)


    def _count_stmt(self, line: int):
        self._stmt_count += 1
        if self._stmt_count > MAX_STATEMENTS:
            raise FALSyntaxError(f"Script exceeds maximum of {MAX_STATEMENTS} statements", line)

    def parse_statement(self) -> Optional[Statement]:
        self.skip_newlines()
        tok = self.peek()
        line = tok.line

        if tok.type == TT.EOF:
            return None

        self._count_stmt(line)

        if tok.type == TT.KW_SET:
            return self.parse_assign()
        if tok.type == TT.KW_IF:
            return self.parse_if()
        if tok.type == TT.KW_FOR:
            return self.parse_for_each()
        if tok.type == TT.KW_REPEAT:
            return self.parse_repeat()
        if tok.type == TT.KW_SWITCH:
            return self.parse_switch()
        if tok.type == TT.KW_STOP:
            return self.parse_stop()
        return self.parse_action()

    def parse_stmt_block(self) -> List[Statement]:
                                                                                                
        self.expect(TT.COLON)
        if not self.check(TT.NEWLINE):
            stmt = self.parse_statement()
            return [stmt] if stmt else []

        self.advance()
        self.skip_newlines()
        self.expect(TT.INDENT, msg="expected indented block after ':'")
        stmts = []
        self.skip_newlines()
        while not self.check(TT.DEDENT, TT.EOF):
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)
            self.skip_newlines()
        self.match(TT.DEDENT)
        return stmts

    def parse_assign(self) -> AssignStmt:
        tok = self.advance()
        name_tok = self.expect(TT.IDENTIFIER, msg="expected variable name after SET")
        self.expect(TT.OP_ASSIGN, msg="expected '=' after variable name")
        value = self.parse_expression()
        return AssignStmt(var=name_tok.value, value=value, line=tok.line)

    def parse_if(self) -> IfStmt:
        line = self.current_line()
        self.advance()
        cond = self.parse_condition()
        body = self.parse_stmt_block()
        branches = [IfBranch(condition=cond, body=body)]
        else_body = []

        while self.check(TT.KW_ELIF):
            self.advance()
            cond2 = self.parse_condition()
            body2 = self.parse_stmt_block()
            branches.append(IfBranch(condition=cond2, body=body2))

        if self.check(TT.KW_ELSE):
            self.advance()
            else_body = self.parse_stmt_block()

        return IfStmt(branches=branches, else_body=else_body, line=line)

    def parse_for_each(self) -> ForEachStmt:
        tok = self.advance()
        self.expect(TT.KW_EACH, msg="expected EACH after FOR")
        var_tok = self.expect(TT.IDENTIFIER, msg="expected variable name after FOR EACH")
        self.expect(TT.KW_IN, msg="expected IN after loop variable")
        iter_tok = self.expect(TT.IDENTIFIER, msg="expected list variable name after IN")
        body = self.parse_stmt_block()
        return ForEachStmt(var=var_tok.value, iterable=iter_tok.value, body=body, line=tok.line)

    def parse_repeat(self) -> RepeatStmt:
        tok = self.advance()
        count_tok = self.expect(TT.INT_LITERAL, msg="expected integer count after REPEAT")
        if count_tok.int_value > MAX_REPEAT:
            raise FALSyntaxError(
                f"REPEAT count {count_tok.int_value} exceeds maximum of {MAX_REPEAT}",
                count_tok.line,
            )
        self.expect(TT.KW_TIMES, msg="expected TIMES after repeat count")
        body = self.parse_stmt_block()
        return RepeatStmt(count=count_tok.int_value, body=body, line=tok.line)

    def parse_switch(self) -> SwitchStmt:
        tok = self.advance()
        expr = self.parse_expression()
        self.expect(TT.COLON)
        self.expect(TT.NEWLINE, msg="expected newline after SWITCH expression:")
        self.skip_newlines()
        self.expect(TT.INDENT, msg="expected indented block after SWITCH:")
        self.skip_newlines()

        cases = []
        default = []

        while not self.check(TT.DEDENT, TT.EOF):
            self.skip_newlines()
            if self.check(TT.KW_CASE):
                self.advance()
                lit = self.parse_literal()
                body = self.parse_stmt_block()
                cases.append(SwitchCase(value=lit, body=body))
            elif self.check(TT.KW_DEFAULT):
                self.advance()
                default = self.parse_stmt_block()
            else:
                break
            self.skip_newlines()

        self.match(TT.DEDENT)
        return SwitchStmt(expr=expr, cases=cases, default=default, line=tok.line)


    def parse_stop(self) -> StopStmt:
        tok = self.advance()
        return StopStmt(line=tok.line)

    def parse_action(self) -> Statement:
        tok = self.peek()
        if tok.type == TT.KW_TRANSFER:
            return self.parse_transfer()
        if tok.type == TT.KW_BUY:
            return self.parse_buy()
        if tok.type == TT.KW_UPGRADE:
            return self.parse_upgrade()
        if tok.type == TT.KW_MOVE:
            return self.parse_move_fleet()
        if tok.type == TT.KW_RENAME:
            return self.parse_rename_fleet()
        if tok.type == TT.KW_FLEET:
            return self.parse_fleet_status_action()
        if tok.type == TT.KW_RECRUIT:
            return self.parse_recruit()
        raise FALSyntaxError(
            f"Unexpected token '{tok.value or tok.type.name}' — expected a statement or action",
            tok.line,
        )

    def parse_transfer(self) -> TransferAction:
        tok = self.advance()
        amount = self.parse_expression()
        res_tok = self.expect(TT.RESOURCE_NAME, msg="expected resource name after amount")
        self.expect(TT.KW_FROM, msg="expected FROM")
        from_world = self.parse_ref()
        self.expect(TT.KW_TO, msg="expected TO")
        to_faction = self.parse_ref()
        self.expect(TT.KW_AT, msg="expected AT after destination faction")
        to_world = self.parse_ref()
        return TransferAction(
            amount=amount, resource=res_tok.value,
            from_world=from_world, to_faction=to_faction, to_world=to_world,
            line=tok.line,
        )

    def parse_buy(self) -> Statement:
        tok = self.advance()
        if self.check(TT.KW_BUILDING):
            self.advance()
            building_ref = self.parse_ref()
            amount = self.parse_expression()
            self.expect(TT.KW_AT, msg="expected AT")
            world = self.parse_ref()
            self.expect(TT.KW_LEVEL, msg="expected LEVEL")
            level = self.parse_expression()
            return BuyBuildingAction(building_ref=building_ref, amount=amount, world=world, level=level, line=tok.line)
        if self.check(TT.KW_VEHICLES):
            self.advance()
            vehicle_ref = self.parse_ref()
            fleet_ref = self.parse_ref()
            amount = self.parse_expression()
            return BuyVehiclesAction(vehicle_ref=vehicle_ref, fleet_ref=fleet_ref, amount=amount, line=tok.line)
        raise FALSyntaxError("expected BUILDING or VEHICLES after BUY", tok.line)

    def parse_upgrade(self) -> UpgradeBuildingAction:
        tok = self.advance()
        self.expect(TT.KW_BUILDING, msg="expected BUILDING after UPGRADE")
        building_ref = self.parse_ref()
        amount = self.parse_expression()
        self.expect(TT.KW_AT, msg="expected AT")
        world = self.parse_ref()
        self.expect(TT.KW_FROM, msg="expected FROM")
        self.expect(TT.KW_LEVEL, msg="expected LEVEL after FROM")
        from_level = self.parse_expression()
        self.expect(TT.KW_TO, msg="expected TO")
        self.expect(TT.KW_LEVEL, msg="expected LEVEL after TO")
        to_level = self.parse_expression()
        return UpgradeBuildingAction(
            building_ref=building_ref, amount=amount, world=world,
            from_level=from_level, to_level=to_level, line=tok.line,
        )

    def parse_move_fleet(self) -> MoveFleetAction:
        tok = self.advance()
        self.expect(TT.KW_FLEET, msg="expected FLEET after MOVE")
        fleet_ref = self.parse_ref()
        self.expect(TT.KW_TO, msg="expected TO")
        dest = self.parse_ref()
        return MoveFleetAction(fleet_ref=fleet_ref, destination=dest, line=tok.line)

    def parse_rename_fleet(self) -> RenameFleetAction:
        tok = self.advance()
        self.expect(TT.KW_FLEET, msg="expected FLEET after RENAME")
        fleet_ref = self.parse_ref()
        self.expect(TT.KW_TO, msg="expected TO")
        new_name = self.parse_expression()
        return RenameFleetAction(fleet_ref=fleet_ref, new_name=new_name, line=tok.line)

    def parse_fleet_status_action(self) -> FleetStatusAction:
        tok = self.advance()
        self.expect(TT.KW_STATUS, msg="expected STATUS after FLEET")
        fleet_ref = self.parse_ref()
        status_tok = self.expect(TT.STATUS_NAME, msg="expected status name (IDLE, MOTHBALLED, etc.)")
        return FleetStatusAction(fleet_ref=fleet_ref, status=status_tok.value, line=tok.line)

    def parse_recruit(self) -> RecruitAction:
        tok = self.advance()
        self.expect(TT.KW_MILITARY, msg="expected MILITARY after RECRUIT")
        amount = self.parse_expression()
        self.expect(TT.KW_COST, msg="expected COST")
        cost = self.parse_expression()
        res_tok = self.expect(TT.RESOURCE_NAME, msg="expected resource name after cost amount")
        self.expect(TT.KW_DURATION, msg="expected DURATION")
        dur_tok = self.expect(TT.DURATION_LITERAL, msg="expected duration (e.g. 2w, 3d, 1mo)")
        self.expect(TT.KW_NAME, msg="expected NAME")
        name_tok = self.expect(TT.STRING_LITERAL, msg="expected quoted name string")
        return RecruitAction(
            amount=amount, cost=cost, resource=res_tok.value,
            duration=dur_tok.value, name=name_tok.value, line=tok.line,
        )


    def parse_condition(self) -> Cond:
        return self.parse_or_cond()

    def parse_or_cond(self) -> Cond:
        left = self.parse_and_cond()
        while self.check(TT.KW_OR):
            self.advance()
            right = self.parse_and_cond()
            left = BinaryCond(left=left, op="OR", right=right, line=self.current_line())
        return left

    def parse_and_cond(self) -> Cond:
        left = self.parse_not_cond()
        while self.check(TT.KW_AND):
            self.advance()
            right = self.parse_not_cond()
            left = BinaryCond(left=left, op="AND", right=right, line=self.current_line())
        return left

    def parse_not_cond(self) -> Cond:
        if self.check(TT.KW_NOT):
            line = self.advance().line
            operand = self.parse_atom_cond()
            return NotCond(operand=operand, line=line)
        return self.parse_atom_cond()

    def parse_atom_cond(self) -> Cond:
        tok = self.peek()
        line = tok.line

        if tok.type == TT.LPAREN:
            self.advance()
            cond = self.parse_condition()
            self.expect(TT.RPAREN)
            return cond

        if tok.type == TT.KW_AT:
            self.advance()
            self.expect(TT.KW_WAR, msg="expected WAR after AT")
            return AtWarCond(line=line)

        if tok.type == TT.KW_BLOCKADED:
            self.advance()
            world = self.parse_ref()
            return BlockadedCond(world=world, line=line)

        if tok.type == TT.KW_TODAY:
            self.advance()
            self.expect(TT.KW_IS, msg="expected IS after TODAY")
            day_tok = self.expect(TT.DAY_NAME, msg="expected day name after TODAY IS")
            return TodayIsCond(day=day_tok.value, line=line)

        if tok.type == TT.KW_FLEET:
            self.advance()
            fleet_ref = self.parse_ref()
            sub = self.peek()
            if sub.type == TT.KW_HEALTH:
                self.advance()
                op = self.parse_compare_op()
                value = self.parse_expression()
                return FleetHealthCond(fleet_ref=fleet_ref, op=op, value=value, line=line)
            if sub.type == TT.KW_STATUS:
                self.advance()
                self.expect(TT.KW_IS, msg="expected IS after FLEET STATUS")
                status_tok = self.expect(TT.STATUS_NAME, msg="expected status name")
                return FleetStatusCond(fleet_ref=fleet_ref, status=status_tok.value, line=line)
            if sub.type == TT.KW_VEHICLES:
                self.advance()
                op = self.parse_compare_op()
                value = self.parse_expression()
                return FleetVehiclesCond(fleet_ref=fleet_ref, op=op, value=value, line=line)
            if sub.type == TT.KW_FACTION:
                self.advance()
                faction_ref = self.parse_ref()
                self.expect(TT.KW_AT, msg="expected AT after FLEET fleet FACTION faction")
                world_ref = self.parse_ref()
                return FleetAtWorldCond(fleet_ref=fleet_ref, faction_ref=faction_ref, world_ref=world_ref, line=line)
            if sub.type == TT.KW_AT:
                self.advance()
                world_ref = self.parse_ref()
                return FleetAtWorldCond(fleet_ref=fleet_ref, faction_ref=None, world_ref=world_ref, line=line)
            raise FALSyntaxError("expected HEALTH, STATUS, VEHICLES, FACTION, or AT after fleet reference", sub.line)

        if tok.type == TT.KW_FACTORY:
            self.advance()
            self.expect(TT.KW_SPACE, msg="expected SPACE after FACTORY")
            self.expect(TT.KW_AT, msg="expected AT after FACTORY SPACE")
            world = self.parse_ref()
            op = self.parse_compare_op()
            value = self.parse_expression()
            return FactorySpaceCond(world=world, op=op, value=value, line=line)

        if tok.type == TT.KW_BUILDINGS:
            self.advance()
            building_ref = self.parse_ref()
            self.expect(TT.KW_AT, msg="expected AT after building reference")
            world = self.parse_ref()
            op = self.parse_compare_op()
            value = self.parse_expression()
            return BuildingCountCond(building_ref=building_ref, world=world, op=op, value=value, line=line)

        if tok.type == TT.KW_WORLD:
            self.advance()
            world_ref = self.parse_ref()
            res_tok = self.expect(TT.RESOURCE_NAME, msg="expected resource name after WORLD world_ref")
            op = self.parse_compare_op()
            value = self.parse_expression()
            return WorldResourceCond(resource=res_tok.value, world_ref=world_ref, op=op, value=value, line=line)

        if tok.type == TT.RESOURCE_NAME:
            self.advance()
            op = self.parse_compare_op()
            value = self.parse_expression()
            return ResourceCond(resource=tok.value, op=op, value=value, line=line)

        left = self.parse_expression()
        op = self.parse_compare_op()
        right = self.parse_expression()
        return ExprComparison(left=left, op=op, right=right, line=line)

    def parse_compare_op(self) -> str:
        tok = self.peek()
        op_map = {
            TT.OP_GT: ">", TT.OP_GTE: ">=", TT.OP_LT: "<",
            TT.OP_LTE: "<=", TT.OP_EQ: "==", TT.OP_NEQ: "!=",
        }
        if tok.type in op_map:
            self.advance()
            return op_map[tok.type]
        raise FALSyntaxError(
            f"expected comparison operator (>, >=, <, <=, ==, !=), got '{tok.value}'",
            tok.line,
        )


    def parse_expression(self) -> Expr:
        left = self.parse_term()
        while self.check(TT.OP_PLUS, TT.OP_MINUS):
            op_tok = self.advance()
            right = self.parse_term()
            left = BinOp(left=left, op=op_tok.value, right=right, line=op_tok.line)
        return left

    def parse_term(self) -> Expr:
        left = self.parse_unary()
        while self.check(TT.OP_STAR, TT.OP_SLASH):
            op_tok = self.advance()
            right = self.parse_unary()
            left = BinOp(left=left, op=op_tok.value, right=right, line=op_tok.line)
        return left

    def parse_unary(self) -> Expr:
        if self.check(TT.OP_MINUS):
            tok = self.advance()
            return UnaryOp(op="-", operand=self.parse_unary(), line=tok.line)
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        tok = self.peek()

        if tok.type == TT.INT_LITERAL:
            self.advance()
            return IntLiteral(value=tok.int_value, line=tok.line)

        if tok.type == TT.STRING_LITERAL:
            self.advance()
            return StrLiteral(value=tok.value, line=tok.line)

        if tok.type == TT.IDENTIFIER:
            self.advance()
            return VarRef(name=tok.value, line=tok.line)

        if tok.type == TT.RESOURCE_NAME:
            self.advance()
            return ResourceExpr(resource=tok.value, line=tok.line)

        if tok.type == TT.KW_FLEETS:
            self.advance()
            self.expect(TT.KW_AT, msg="expected AT after FLEETS")
            world = self.parse_ref()
            return FleetsAtExpr(world=world, line=tok.line)

        if tok.type == TT.KW_RANDI:
            self.advance()
            self.expect(TT.LPAREN, msg="expected ( after RANDI")
            low = self.parse_expression()
            self.expect(TT.COMMA, msg="expected , between RANDI arguments")
            high = self.parse_expression()
            self.expect(TT.RPAREN, msg="expected ) after RANDI arguments")
            return RandiExpr(low=low, high=high, line=tok.line)

        if tok.type == TT.KW_ORDINAL:
            self.advance()
            self.expect(TT.LPAREN, msg="expected ( after ORDINAL")
            operand = self.parse_expression()
            self.expect(TT.RPAREN, msg="expected ) after ORDINAL argument")
            return OrdinalExpr(operand=operand, line=tok.line)

        if tok.type == TT.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TT.RPAREN)
            return expr

        raise FALSyntaxError(
            f"expected expression, got '{tok.value or tok.type.name}'",
            tok.line,
        )

    def parse_ref(self) -> Expr:
                                                                                           
        tok = self.peek()
        if tok.type == TT.STRING_LITERAL:
            self.advance()
            return StrLiteral(value=tok.value, line=tok.line)
        if tok.type == TT.INT_LITERAL:
            self.advance()
            return IntLiteral(value=tok.int_value, line=tok.line)
        if tok.type == TT.IDENTIFIER:
            self.advance()
            return VarRef(name=tok.value, line=tok.line)
        raise FALSyntaxError(
            f"expected name or number, got '{tok.value or tok.type.name}'",
            tok.line,
        )

    def parse_literal(self) -> Literal:
        tok = self.peek()
        if tok.type == TT.INT_LITERAL:
            self.advance()
            return IntLiteral(value=tok.int_value, line=tok.line)
        if tok.type == TT.STRING_LITERAL:
            self.advance()
            return StrLiteral(value=tok.value, line=tok.line)
        raise FALSyntaxError(
            f"expected literal value, got '{tok.value or tok.type.name}'",
            tok.line,
        )
