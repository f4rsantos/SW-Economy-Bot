import math

IRL_SECONDS_PER_GAME_YEAR = 2629800
CALIBRATION_DISTANCE_UNITS = 1.65
CALIBRATION_TIME_HOURS = 1.0
INTER_SYSTEM_TRAVEL_DAYS = 14
ALIGNMENT_EPOCH_STR = "1982-03-10T00:00:00+00:00"


def calculate_speed(period_in_game_years: float) -> float:
    if period_in_game_years == 0:
        return 0.0
    return (2 * math.pi) / (period_in_game_years * IRL_SECONDS_PER_GAME_YEAR)


def _body(a, period, *, e=0.0, incl=0.0, raan=0.0, argp=0.0, m0=0.0, parent=None):
    return {
        "dist": a,
        "a": a,
        "period": period,
        "speed": calculate_speed(period),
        "e": e,
        "i": math.radians(incl),
        "raan": math.radians(raan),
        "argp": math.radians(argp),
        "m0": m0,
        "parent": parent,
    }


SOL_ORBITAL_DATA = {
    "Mercury": _body(0.39, 0.241, e=0.2056, incl=7.005, raan=48.331, argp=29.126),
    "Venus":   _body(0.72, 0.615, e=0.0068, incl=3.395, raan=76.680, argp=54.920),
    "Earth":   _body(1.00, 1.0,   e=0.0167, incl=0.0,   raan=0.0,    argp=102.937),
    "Mars":    _body(1.52, 1.88,  e=0.0934, incl=1.850, raan=49.559, argp=286.500),
    "Jupiter": _body(5.20, 11.86, e=0.0484, incl=1.305, raan=100.474, argp=274.254),
    "Saturn":  _body(9.58, 29.45, e=0.0539, incl=2.486, raan=113.662, argp=338.940),
    "Uranus":  _body(19.20, 84.02, e=0.0473, incl=0.773, raan=74.017, argp=96.937),
    "Neptune": _body(30.05, 164.8, e=0.0086, incl=1.770, raan=131.784, argp=273.180),
    "Pluto":   _body(39.50, 248.0, e=0.2488, incl=17.160, raan=110.299, argp=113.770),

    "Ceres":                _body(2.77, 4.6, e=0.0758, incl=10.59, raan=80.31, argp=73.6, m0=0.785),
    "Asteroid Belt Area B": _body(2.77, 4.6, m0=2.356),
    "Asteroid Belt Area C": _body(2.77, 4.6, m0=3.927),
    "Asteroid Belt Area A": _body(2.77, 4.6, m0=5.497),

    "Luna":     _body(0.00257, 0.0748, e=0.0549, incl=5.145, parent="Earth"),
    "Io":       _body(0.00282, 0.0048, e=0.0041, incl=0.036, parent="Jupiter"),
    "Europa":   _body(0.00448, 0.0097, e=0.0090, incl=0.466, parent="Jupiter"),
    "Ganymede": _body(0.00715, 0.0196, e=0.0013, incl=0.177, parent="Jupiter"),
    "Callisto": _body(0.01258, 0.0457, e=0.0074, incl=0.192, parent="Jupiter"),
    "Mimas":     _body(0.00123, 0.0025, e=0.0196, incl=1.574, parent="Saturn"),
    "Enceladus": _body(0.00159, 0.0037, e=0.0047, incl=0.009, parent="Saturn"),
    "Tethys":    _body(0.00196, 0.0051, e=0.0001, incl=1.120, parent="Saturn"),
    "Dione":     _body(0.00252, 0.0075, e=0.0022, incl=0.019, parent="Saturn"),
    "Rhea":      _body(0.00352, 0.0123, e=0.0013, incl=0.345, parent="Saturn"),
    "Titan":     _body(0.00816, 0.0435, e=0.0288, incl=0.348, parent="Saturn"),
    "Iapetus":   _body(0.02380, 0.2171, e=0.0276, incl=15.470, parent="Saturn"),
    "Miranda": _body(0.00086, 0.0038, e=0.0013, incl=4.232, parent="Uranus"),
    "Ariel":   _body(0.00127, 0.0068, e=0.0012, incl=0.260, parent="Uranus"),
    "Umbriel": _body(0.00178, 0.0112, e=0.0039, incl=0.128, parent="Uranus"),
    "Titania": _body(0.00291, 0.0238, e=0.0011, incl=0.340, parent="Uranus"),
    "Oberon":  _body(0.00390, 0.0369, e=0.0014, incl=0.058, parent="Uranus"),
    "Proteus": _body(0.00078, 0.0030, e=0.0005, incl=0.524, parent="Neptune"),
    "Triton":  _body(0.00237, 0.0160, e=0.0000, incl=156.885, parent="Neptune"),
    "Nereid":  _body(0.03685, 0.9860, e=0.7507, incl=7.090, parent="Neptune"),
    "Charon":  _body(0.00013, 0.0175, e=0.0002, incl=0.080, parent="Pluto"),
}

CORELLI_ORBITAL_DATA = {
    "Barcas":     _body(0.0455, 0.5,  e=0.041, incl=1.8, raan=42.0, argp=118.0),
    "Deo Gloria": _body(0.0259, 1.2,  e=0.012, incl=0.6, raan=204.0, argp=31.0),
    "Novai":      _body(1.956, 3.5,   e=0.088, incl=3.4, raan=156.0, argp=287.0),
    "Scipios":    _body(0.0470, 15.0, e=0.137, incl=2.2, raan=311.0, argp=74.0),
    "Asteroid Belt Area 1": _body(2.10, 2.5, m0=0.785),
    "Asteroid Belt Area 2": _body(2.10, 2.5, m0=2.356),
    "Asteroid Belt Area 3": _body(2.10, 2.5, m0=3.927),
    "Vesta": _body(2.10, 2.5, e=0.089, incl=7.14, raan=103.8, argp=151.2, m0=5.497),
}

SYSTEMS_DATA = {
    "Sol": SOL_ORBITAL_DATA,
    "Corelli": CORELLI_ORBITAL_DATA
}
