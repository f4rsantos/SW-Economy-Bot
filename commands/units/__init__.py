from discord import app_commands


class UnitGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="unit", description="Unit management commands")


class VehicleGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="vehicle", description="Vehicle management commands")


async def setup(bot):
    from commands.units import (
        listUnits, unitCreate, deleteUnit, unitRename, unitMove, unitStatus,
        buyVehicle, listVehicles, renameVehicle, deregisterVehicle, transferVehicle,
        setVehicleType, factoryProgress, vehicleAdmin, repairUnit, damageUnit,
        unitType
    )

    unit_group = UnitGroup()
    unit_group.add_command(listUnits.list_units)
    unit_group.add_command(unitCreate.unit_create)
    unit_group.add_command(deleteUnit.unit_delete)
    unit_group.add_command(unitRename.unit_rename)
    unit_group.add_command(unitMove.unit_move)
    unit_group.add_command(unitStatus.unit_status_command)
    unit_group.add_command(factoryProgress.factory_progress)
    unit_group.add_command(repairUnit.repair_unit_cmd)
    unit_group.add_command(damageUnit.damage_unit_cmd)
    unit_group.add_command(unitType.unit_set_type)

    vehicle_group = VehicleGroup()
    vehicle_group.add_command(buyVehicle.buy_vehicle_cmd)
    vehicle_group.add_command(listVehicles.list_vehicles)
    vehicle_group.add_command(renameVehicle.rename_vehicle)
    vehicle_group.add_command(deregisterVehicle.deregister_vehicle)
    vehicle_group.add_command(transferVehicle.transfer_vehicle_cmd)
    vehicle_group.add_command(setVehicleType.set_vehicle_type)
    vehicle_group.add_command(vehicleAdmin.buy_vehicle_free)
    vehicle_group.add_command(vehicleAdmin.refund_vehicle_cmd)

    bot.tree.add_command(unit_group)
    bot.tree.add_command(vehicle_group)
