# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Dict
import math

_ROLE_MULT = {
    'fighter':   {'er': 1.0, 'cm': 1.0, 'el': 1.0},
    'bomber':    {'er': 1.3, 'cm': 0.9, 'el': 0.8},
    'transport': {'er': 1.0, 'cm': 0.7, 'el': 0.6},
    'drone':     {'er': 1.0, 'cm': 1.0, 'el': 1.0},
    'gunship':   {'er': 1.2, 'cm': 1.1, 'el': 0.9}
}


def rate_aircraft(data: Dict) -> Dict[str, int]:
    length = data['length']
    aircraft_type = data['aircraft_type']
    weapons = data.get('weapons', False)
    guns = data.get('guns', 0)
    stealth = data.get('stealth', 'none')
    engines = data.get('engines', 1)
    systems = data.get('systems', 0)
    ordnance_kg = data.get('ordnance_kg', 0)
    cargo = data.get('cargo', 0)
    helicopter = data.get('helicopter', False)
    radar = data.get('radar', 'normal')
    flight_type = data.get('flight_type', 'air')
    capability = data.get('capability', 'none')
    speed_mach = data.get('speed_mach') or 0
    shield = data.get('shield', False)
    other = data.get('other', 0)

    if aircraft_type == "fighter":
        Base_CM = length * 5.4
        Base_EL = length * 31.88
    else:
        Base_CM = length * 1.1
        Base_EL = length * 2.2

    Base_ER = (length ** 2) / 120 + length * 220000 + 15000000
    CS = 60

    mult = _ROLE_MULT.get(aircraft_type, {'er': 1.0, 'cm': 1.0, 'el': 1.0})
    Base_ER *= mult['er']
    Base_CM *= mult['cm']
    Base_EL *= mult['el']

    Base_ER += 500000 * engines
    Base_EL += 5 * engines
    CS += 2 * engines

    if weapons:
        Base_ER *= 1.6
        Base_CM *= 1.3
        CS += 6

    if helicopter:
        Base_ER *= 0.6
        Base_CM *= 0.8
        CS *= 0.9

    if aircraft_type == "drone":
        Base_ER *= 0.4
        Base_CM *= 0.4
        Base_EL *= 0.5
        CS *= 0.6

    if stealth == "yes":
        Base_ER *= 2.0
        Base_EL *= 1.2
        CS *= 1.2
    elif stealth == "low":
        Base_ER *= 1.15
        Base_EL += 10
        CS += 2

    if radar == "AEW":
        Base_ER += 4000000
        Base_CM += 10
        Base_EL += 20
        CS += 3

    Base_ER += 600 * cargo

    if flight_type == "hybrid":
        Base_ER *= 1.2
        Base_EL *= 1.2
        CS *= 1.1
    elif flight_type == "space":
        Base_ER *= 1.5
        Base_EL *= 1.3
        CS *= 1.2

    if shield:
        Base_ER += 5000000
        Base_EL += 10
        CS += 2

    Base_ER += 150000 * (ordnance_kg / 100)
    Base_ER += 250000 * guns
    Base_EL += 2 * guns
    CS += guns

    Base_ER += 300000 * systems
    Base_EL += 1.5 * systems
    CS += 12 * systems

    if capability == "STOL":
        Base_ER *= 1.1
        Base_EL += 5
        CS += 2
    elif capability == "VTOL":
        Base_ER *= 1.25
        Base_EL += 15
        CS += 5

    if flight_type in ["air", "hybrid"]:
        thresholds = {
            'fighter': 2.5, 'bomber': 2.0, 'transport': 1.0, 'gunship': 1.0
        }
        threshold = thresholds.get(aircraft_type, 1.0 if helicopter else None)
        if threshold is not None and speed_mach > threshold:
            Base_ER *= 1 + ((speed_mach - threshold) * 1.1) ** 2

    if flight_type == "air":
        Base_ER += speed_mach * 6000000
    elif flight_type == "hybrid":
        Base_ER += speed_mach * 4000000

    if aircraft_type == "transport":
        Base_ER *= 4.0
    if helicopter:
        Base_ER *= 1.15

    return {
        'ER': int(math.ceil(Base_ER + other)),
        'CM': int(math.ceil(Base_CM)),
        'EL': int(math.ceil(Base_EL)),
        'CS': int(math.ceil(CS))
    }
