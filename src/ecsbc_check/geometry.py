"""Polygon geometry for EnergyPlus surfaces: area, outward normal, azimuth and tilt."""

from __future__ import annotations

import math
from dataclasses import dataclass

Vertex = tuple[float, float, float]


@dataclass(frozen=True)
class Orientation:
    area: float  # m2
    azimuth: float  # degrees clockwise from true north, 0-360
    tilt: float  # degrees from horizontal-up: 0 = roof facing sky, 90 = wall, 180 = floor


def newell_normal(vertices: list[Vertex]) -> tuple[float, float, float]:
    """Unnormalised polygon normal by Newell's method.

    Follows the right-hand rule: counter-clockwise vertices (seen from outside)
    give the outward normal. Its length equals twice the polygon area.
    """
    nx = ny = nz = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1, z1 = vertices[i]
        x2, y2, z2 = vertices[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


def orientation(
    vertices: list[Vertex],
    north_axis_deg: float = 0.0,
    clockwise: bool = False,
) -> Orientation:
    """Area, true azimuth and tilt of a planar polygon.

    north_axis_deg is the EnergyPlus Building North Axis (plus any zone
    relative north): the angle, clockwise, from true north to the model's +Y axis.
    Set clockwise=True when GlobalGeometryRules says vertices are clockwise.
    """
    if len(vertices) < 3:
        raise ValueError("a surface needs at least 3 vertices")
    nx, ny, nz = newell_normal(vertices)
    if clockwise:
        nx, ny, nz = -nx, -ny, -nz
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length == 0:
        raise ValueError("degenerate surface (zero area)")
    area = length / 2.0
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, nz / length))))
    if math.hypot(nx, ny) < 1e-9 * length:
        azimuth = 0.0  # horizontal surface: azimuth is meaningless
    else:
        azimuth = (math.degrees(math.atan2(nx, ny)) + north_axis_deg) % 360.0
    return Orientation(area=area, azimuth=azimuth, tilt=tilt)


def facade(azimuth: float) -> str:
    """Name the facade an azimuth falls in, using 90-degree sectors centred on N, E, S, W."""
    a = azimuth % 360.0
    if a >= 315.0 or a < 45.0:
        return "North"
    if a < 135.0:
        return "East"
    if a < 225.0:
        return "South"
    return "West"


def is_north_facing(azimuth: float, half_angle: float = 45.0) -> bool:
    """True when the outward normal lies within +/- half_angle degrees of true north."""
    a = azimuth % 360.0
    return a <= half_angle or a >= 360.0 - half_angle
