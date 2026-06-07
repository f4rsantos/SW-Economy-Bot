import math

IRL_SECONDS_PER_GAME_YEAR = 2629800
CALIBRATION_DISTANCE_UNITS = 165.0
CALIBRATION_TIME_HOURS = 1.0
INTER_SYSTEM_TRAVEL_DAYS = 14
ALIGNMENT_EPOCH_STR = "1982-03-10T00:00:00+00:00"


def calculate_speed(period_in_game_years: float) -> float:
    if period_in_game_years == 0:
        return 0.0
    return (2 * math.pi) / (period_in_game_years * IRL_SECONDS_PER_GAME_YEAR)


SOL_ORBITAL_DATA = {
    "Mercury": {"dist": 39,   "period": 0.241, "speed": calculate_speed(0.241), "parent": None},
    "Venus":   {"dist": 72,   "period": 0.615, "speed": calculate_speed(0.615), "parent": None},
    "Earth":   {"dist": 100,  "period": 1.0,   "speed": calculate_speed(1.0),   "parent": None},
    "Mars":    {"dist": 152,  "period": 1.88,  "speed": calculate_speed(1.88),  "parent": None},
    "Jupiter": {"dist": 520,  "period": 11.86, "speed": calculate_speed(11.86), "parent": None},
    "Saturn":  {"dist": 958,  "period": 29.45, "speed": calculate_speed(29.45), "parent": None},
    "Uranus":  {"dist": 1920, "period": 84.02, "speed": calculate_speed(84.02), "parent": None},
    "Neptune": {"dist": 3005, "period": 164.8, "speed": calculate_speed(164.8), "parent": None},
    "Pluto":   {"dist": 3950, "period": 248.0, "speed": calculate_speed(248.0), "parent": None},

    "Ceres":                {"dist": 277, "speed": calculate_speed(4.6), "angle": 0.785, "parent": None},
    "Asteroid Belt Area B": {"dist": 277, "speed": calculate_speed(4.6), "angle": 2.356, "parent": None},
    "Asteroid Belt Area C": {"dist": 277, "speed": calculate_speed(4.6), "angle": 3.927, "parent": None},
    "Asteroid Belt Area A": {"dist": 277, "speed": calculate_speed(4.6), "angle": 5.497, "parent": None},

    "Luna":     {"parent": "Earth",   "dist": 0.257, "speed": calculate_speed(0.0748)},
    "Io":       {"parent": "Jupiter", "dist": 0.282, "speed": calculate_speed(0.0048)},
    "Europa":   {"parent": "Jupiter", "dist": 0.448, "speed": calculate_speed(0.0097)},
    "Ganymede": {"parent": "Jupiter", "dist": 0.715, "speed": calculate_speed(0.0196)},
    "Callisto": {"parent": "Jupiter", "dist": 1.258, "speed": calculate_speed(0.0457)},
    "Mimas":     {"parent": "Saturn", "dist": 0.123, "speed": calculate_speed(0.0025)},
    "Enceladus": {"parent": "Saturn", "dist": 0.159, "speed": calculate_speed(0.0037)},
    "Tethys":    {"parent": "Saturn", "dist": 0.196, "speed": calculate_speed(0.0051)},
    "Dione":     {"parent": "Saturn", "dist": 0.252, "speed": calculate_speed(0.0075)},
    "Rhea":      {"parent": "Saturn", "dist": 0.352, "speed": calculate_speed(0.0123)},
    "Titan":     {"parent": "Saturn", "dist": 0.816, "speed": calculate_speed(0.0435)},
    "Iapetus":   {"parent": "Saturn", "dist": 2.380, "speed": calculate_speed(0.2171)},
    "Miranda": {"parent": "Uranus", "dist": 0.086, "speed": calculate_speed(0.0038)},
    "Ariel":   {"parent": "Uranus", "dist": 0.127, "speed": calculate_speed(0.0068)},
    "Umbriel": {"parent": "Uranus", "dist": 0.178, "speed": calculate_speed(0.0112)},
    "Titania": {"parent": "Uranus", "dist": 0.291, "speed": calculate_speed(0.0238)},
    "Oberon":  {"parent": "Uranus", "dist": 0.390, "speed": calculate_speed(0.0369)},
    "Proteus": {"parent": "Neptune", "dist": 0.078, "speed": calculate_speed(0.0030)},
    "Triton":  {"parent": "Neptune", "dist": 0.237, "speed": calculate_speed(0.0160)},
    "Nereid":  {"parent": "Neptune", "dist": 3.685, "speed": calculate_speed(0.9860)},
    "Charon":  {"parent": "Pluto",   "dist": 0.013, "speed": calculate_speed(0.0175)},
}

CORELLI_ORBITAL_DATA = {
    "Barcas":     {"dist": 4.55,  "speed": calculate_speed(0.5),  "parent": None},
    "Deo Gloria": {"dist": 2.59, "speed": calculate_speed(1.2),  "parent": None},
    "Novai":      {"dist": 195.6, "speed": calculate_speed(3.5),  "parent": None},
    "Scipios":    {"dist": 4.70, "speed": calculate_speed(15.0), "parent": None},
    "Asteroid Belt Area 1": {"dist": 210, "speed": calculate_speed(2.5), "angle": 0.785, "parent": None},
    "Asteroid Belt Area 2": {"dist": 210, "speed": calculate_speed(2.5), "angle": 2.356, "parent": None},
    "Asteroid Belt Area 3": {"dist": 210, "speed": calculate_speed(2.5), "angle": 3.927, "parent": None},
    "Vesta": {"dist": 210, "speed": calculate_speed(2.5), "angle": 5.497, "parent": None},
}

SYSTEMS_DATA = {
    "Sol": SOL_ORBITAL_DATA,
    "Corelli": CORELLI_ORBITAL_DATA
}
