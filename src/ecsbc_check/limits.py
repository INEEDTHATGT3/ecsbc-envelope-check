"""ECSBC 2024 prescriptive building-envelope limits (commercial buildings).

Source: Energy Conservation and Sustainable Building Code 2024, Bureau of Energy
Efficiency (BEE), Section 5.3, Tables 5.3 to 5.11 and 5.15. Values were transcribed
by hand: check them against the notified code, and against your state's own
amendments, before relying on a result.

Zones follow the code's order: composite, hot_dry, warm_humid, temperate, cold.
Levels: "ecsbc" (ECSBC compliant), "ecsbc_plus" (ECSBC+), "super" (Super ECSBC).
U-factors are in W/m2K.
"""

from __future__ import annotations

ZONES = ("composite", "hot_dry", "warm_humid", "temperate", "cold")
LEVELS = ("ecsbc", "ecsbc_plus", "super")
BUILDING_TYPES = (
    "default",
    "assembly_hospitality_large",  # roof only: Assembly / Hospitality > 10,000 m2 AGA
    "no_star_hotel_small",  # walls only: No Star Hotel < 10,000 m2 AGA
    "business_small",  # walls only: Business < 10,000 m2 AGA
    "school_small",  # walls only: School < 10,000 m2 AGA
)


def _z(composite, hot_dry, warm_humid, temperate, cold):
    return dict(zip(ZONES, (composite, hot_dry, warm_humid, temperate, cold)))


ROOF_U = {
    "ecsbc": {  # Table 5.3
        "default": _z(0.26, 0.26, 0.26, 0.26, 0.20),
        "assembly_hospitality_large": _z(0.20, 0.20, 0.20, 0.20, 0.20),
    },
    "ecsbc_plus": {"default": _z(0.20, 0.20, 0.20, 0.20, 0.20)},  # ECSBC+ roof table
    "super": {"default": _z(0.18, 0.18, 0.18, 0.18, 0.18)},  # Table 5-5
}

WALL_U = {
    "ecsbc": {  # Table 5.6
        "default": _z(0.40, 0.40, 0.40, 0.55, 0.34),
        "no_star_hotel_small": _z(0.63, 0.63, 0.63, 0.63, 0.40),
        "business_small": _z(0.63, 0.63, 0.63, 0.63, 0.40),
        "school_small": _z(0.85, 0.85, 0.85, 1.00, 0.40),
    },
    "ecsbc_plus": {  # Table 5.7
        "default": _z(0.34, 0.34, 0.34, 0.55, 0.22),
        "no_star_hotel_small": _z(0.44, 0.44, 0.44, 0.44, 0.34),
        "business_small": _z(0.44, 0.44, 0.44, 0.55, 0.34),
        "school_small": _z(0.63, 0.63, 0.63, 0.75, 0.44),
    },
    "super": {"default": _z(0.22, 0.22, 0.22, 0.22, 0.22)},  # Table 5.8
}

FENESTRATION = {
    "ecsbc": {  # Table 5.9
        "u": _z(2.20, 2.20, 2.20, 3.00, 1.80),
        "shgc_non_north": _z(0.25, 0.25, 0.25, 0.25, 0.62),
        "shgc_north_lat_ge_15": _z(0.50, 0.50, 0.50, 0.50, 0.62),
        "shgc_north_lat_lt_15": _z(0.25, 0.25, 0.25, 0.25, 0.62),
    },
    "ecsbc_plus": {  # Table 5.10
        "u": _z(1.80, 1.80, 1.80, 2.20, 1.80),
        "shgc_non_north": _z(0.25, 0.25, 0.25, 0.25, 0.62),
        "shgc_north_lat_ge_15": _z(0.50, 0.50, 0.50, 0.50, 0.62),
        "shgc_north_lat_lt_15": _z(0.25, 0.25, 0.25, 0.25, 0.62),
    },
    "super": {  # Table 5.11
        "u": _z(1.80, 1.80, 1.80, 2.20, 1.80),
        "shgc_non_north": _z(0.20, 0.20, 0.20, 0.20, 0.62),
        "shgc_north_lat_ge_15": _z(0.50, 0.50, 0.50, 0.50, 0.62),
        "shgc_north_lat_lt_15": _z(0.20, 0.20, 0.20, 0.20, 0.62),
    },
}

MAX_WWR = 0.40  # Section 5.3.3, Standardized Method
MIN_VLT = 0.27  # Section 5.3.3
MAX_SRR = 0.05  # Section 5.3.4
SKYLIGHT_MAX_U = 4.25  # Table 5.15, all zones
SKYLIGHT_MAX_SHGC = 0.35  # Table 5.15, all zones

TABLE_REF = {
    ("roof", "ecsbc"): "ECSBC 2024 Table 5.3",
    ("roof", "ecsbc_plus"): "ECSBC 2024 §5.3.1 (ECSBC+ roof table)",
    ("roof", "super"): "ECSBC 2024 Table 5-5",
    ("wall", "ecsbc"): "ECSBC 2024 Table 5.6",
    ("wall", "ecsbc_plus"): "ECSBC 2024 Table 5.7",
    ("wall", "super"): "ECSBC 2024 Table 5.8",
    ("window", "ecsbc"): "ECSBC 2024 Table 5.9",
    ("window", "ecsbc_plus"): "ECSBC 2024 Table 5.10",
    ("window", "super"): "ECSBC 2024 Table 5.11",
    ("wwr", None): "ECSBC 2024 §5.3.3",
    ("vlt", None): "ECSBC 2024 §5.3.3",
    ("srr", None): "ECSBC 2024 §5.3.4",
    ("skylight", None): "ECSBC 2024 Table 5.15",
}


def _check(zone: str, level: str) -> None:
    if zone not in ZONES:
        raise ValueError(f"unknown climate zone {zone!r}; use one of {ZONES}")
    if level not in LEVELS:
        raise ValueError(f"unknown compliance level {level!r}; use one of {LEVELS}")


def roof_u_limit(zone: str, level: str = "ecsbc", building_type: str = "default") -> float:
    _check(zone, level)
    table = ROOF_U[level]
    return table.get(building_type, table["default"])[zone]


def wall_u_limit(zone: str, level: str = "ecsbc", building_type: str = "default") -> float:
    _check(zone, level)
    table = WALL_U[level]
    return table.get(building_type, table["default"])[zone]


def window_u_limit(zone: str, level: str = "ecsbc") -> float:
    _check(zone, level)
    return FENESTRATION[level]["u"][zone]


def window_shgc_limit(zone: str, level: str, north: bool, latitude: float) -> float:
    _check(zone, level)
    table = FENESTRATION[level]
    if not north:
        return table["shgc_non_north"][zone]
    key = "shgc_north_lat_ge_15" if latitude >= 15.0 else "shgc_north_lat_lt_15"
    return table[key][zone]
