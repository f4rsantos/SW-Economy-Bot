# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from discord import app_commands


class UnitGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="unit", description="Unit management commands")


class VehicleGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="vehicle", description="Vehicle management commands")


async def setup(bot):
    from commands.units import (
        list_units, unit_create, delete_unit, unit_rename, unit_move, unit_status,
        buy_vehicle, list_vehicles, rename_vehicle, deregister_vehicle, transfer_vehicle,
        set_vehicle_type, factory_progress, vehicle_admin, repair_unit, damage_unit,
        unit_type, refit, unit_number, vehicle_number
    )

    unit_group = UnitGroup()
    unit_group.add_command(list_units.list_units)
    unit_group.add_command(unit_create.unit_create)
    unit_group.add_command(delete_unit.unit_delete)
    unit_group.add_command(unit_rename.unit_rename)
    unit_group.add_command(unit_move.unit_move)
    unit_group.add_command(unit_status.unit_status_command)
    unit_group.add_command(factory_progress.factory_progress)
    unit_group.add_command(repair_unit.repair_unit_cmd)
    unit_group.add_command(damage_unit.damage_unit_cmd)
    unit_group.add_command(unit_type.unit_set_type)
    unit_group.add_command(unit_number.unit_number)

    vehicle_group = VehicleGroup()
    vehicle_group.add_command(buy_vehicle.buy_vehicle_cmd)
    vehicle_group.add_command(list_vehicles.list_vehicles)
    vehicle_group.add_command(rename_vehicle.rename_vehicle)
    vehicle_group.add_command(deregister_vehicle.deregister_vehicle)
    vehicle_group.add_command(transfer_vehicle.transfer_vehicle_cmd)
    vehicle_group.add_command(set_vehicle_type.set_vehicle_type)
    vehicle_group.add_command(vehicle_admin.buy_vehicle_free)
    vehicle_group.add_command(vehicle_admin.refund_vehicle_cmd)
    vehicle_group.add_command(refit.refit_cmd)
    vehicle_group.add_command(vehicle_number.vehicle_number)

    bot.tree.add_command(unit_group)
    bot.tree.add_command(vehicle_group)
