"""Turn a parsed IDF into envelope surfaces, windows and constructions."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Orientation, Vertex, orientation
from .idf import IDF, to_float

# Outside-boundary-condition keywords. Used to tell whether a BuildingSurface:Detailed
# object has the 'Space Name' field that EnergyPlus 22.1 and later insert after 'Zone Name'.
_BOUNDARY_WORDS = {
    "outdoors",
    "ground",
    "surface",
    "zone",
    "adiabatic",
    "foundation",
    "othersidecoefficients",
    "othersideconditionsmodel",
    "kiva",
}

# ISO 6946 surface resistances, m2K/W (Rse outside; Rsi inside by heat-flow direction)
RSE = 0.04
RSI_HORIZONTAL = 0.13  # walls
RSI_UPWARD = 0.10  # roofs
RSI_DOWNWARD = 0.17  # floors


@dataclass
class Surface:
    name: str
    surface_type: str
    construction: str
    zone: str
    boundary: str
    geometry: Orientation
    multiplier: float = 1.0

    @property
    def area(self) -> float:
        return self.geometry.area * self.multiplier

    @property
    def is_exterior(self) -> bool:
        return self.boundary.lower() == "outdoors"

    @property
    def kind(self) -> str:
        """'roof', 'wall' or 'floor', from tilt (roof if sloped under 60 degrees)."""
        tilt = self.geometry.tilt
        if tilt < 60.0:
            return "roof"
        if tilt <= 120.0:
            return "wall"
        return "floor"


@dataclass
class Window:
    name: str
    fenestration_type: str
    construction: str
    parent: str
    geometry: Orientation
    multiplier: float = 1.0

    @property
    def area(self) -> float:
        return self.geometry.area * self.multiplier


@dataclass
class GlazingProps:
    u: float
    shgc: float
    vlt: float | None
    source: str


def _is_number(value: str) -> bool:
    return to_float(value) is not None


def extract_vertices(fields: list[str], first_possible: int) -> tuple[list[Vertex], int]:
    """Find the vertex list at the end of a surface object.

    Returns the vertices and the index of the 'Number of Vertices' field. Works
    whether that field holds a count or is blank / 'autocalculate', and whatever
    optional fields different EnergyPlus versions put before it.
    """
    trimmed = list(fields)
    while trimmed and trimmed[-1] == "":
        trimmed.pop()

    for k in range(first_possible, len(trimmed)):
        n = to_float(trimmed[k])
        if n is None or n < 3 or n != int(n):
            continue
        coords = trimmed[k + 1 :]
        if len(coords) == 3 * int(n) and all(_is_number(c) for c in coords):
            return _triples(coords), k

    # Number of Vertices left blank or 'autocalculate': coordinates are the trailing numeric run
    j = len(trimmed) - 1
    while j >= first_possible and _is_number(trimmed[j]):
        j -= 1
    coords = trimmed[j + 1 :]
    if len(coords) >= 9 and len(coords) % 3 == 0:
        return _triples(coords), j
    raise ValueError("could not find vertex coordinates")


def _triples(coords: list[str]) -> list[Vertex]:
    values = [float(c) for c in coords]
    return [(values[i], values[i + 1], values[i + 2]) for i in range(0, len(values), 3)]


@dataclass
class EnvelopeModel:
    surfaces: list[Surface]
    windows: list[Window]
    opaque_r: dict[str, float]  # construction name (upper) -> sum of layer R, m2K/W
    missing_layers: dict[str, list[str]]  # construction name (upper) -> unresolved layer names
    glazing: dict[str, GlazingProps]  # construction name (upper) -> simple glazing props
    latitude: float | None
    north_axis: float
    warnings: list[str]


def load_envelope(idf: IDF) -> EnvelopeModel:
    warnings: list[str] = []

    site = idf.first("Site:Location")
    latitude = to_float(site.get(1)) if site else None

    building = idf.first("Building")
    north_axis = to_float(building.get(1), 0.0) if building else 0.0

    rules = idf.first("GlobalGeometryRules")
    clockwise = False
    relative = True
    if rules:
        clockwise = rules.get(1).lower() == "clockwise"
        relative = rules.get(2).lower() == "relative" or rules.get(2) == ""

    zones = {}
    for z in idf.all("Zone"):
        rel_north = to_float(z.get(1), 0.0) if relative else 0.0
        mult = to_float(z.get(6), 1.0) or 1.0
        zones[z.name.upper()] = (rel_north, mult)

    surfaces: list[Surface] = []
    for obj in idf.all("BuildingSurface:Detailed"):
        bc_index = 4 if obj.get(4).lower() in _BOUNDARY_WORDS or obj.get(4).lower().startswith("ground") else 5
        try:
            verts, _ = extract_vertices(obj.fields, bc_index + 5)
        except ValueError:
            warnings.append(f"Skipped surface {obj.name!r}: no readable vertices")
            continue
        rel_north, mult = zones.get(obj.get(3).upper(), (0.0, 1.0))
        geo = orientation(verts, north_axis + rel_north, clockwise)
        surfaces.append(
            Surface(
                name=obj.name,
                surface_type=obj.get(1),
                construction=obj.get(2),
                zone=obj.get(3),
                boundary=obj.get(bc_index),
                geometry=geo,
                multiplier=mult,
            )
        )

    surfaces_by_name = {s.name.upper(): s for s in surfaces}
    windows: list[Window] = []
    for obj in idf.all("FenestrationSurface:Detailed"):
        try:
            verts, nv_index = extract_vertices(obj.fields, 6)
        except ValueError:
            warnings.append(f"Skipped window {obj.name!r}: no readable vertices")
            continue
        parent = surfaces_by_name.get(obj.get(3).upper())
        rel_north, zone_mult = (0.0, 1.0)
        if parent is not None:
            rel_north, zone_mult = zones.get(parent.zone.upper(), (0.0, 1.0))
        own_mult = to_float(obj.get(nv_index - 1), 1.0) or 1.0
        geo = orientation(verts, north_axis + rel_north, clockwise)
        windows.append(
            Window(
                name=obj.name,
                fenestration_type=obj.get(1),
                construction=obj.get(2),
                parent=obj.get(3),
                geometry=geo,
                multiplier=own_mult * zone_mult,
            )
        )

    opaque_r, missing, glazing = _constructions(idf)
    return EnvelopeModel(surfaces, windows, opaque_r, missing, glazing, latitude, north_axis, warnings)


def _constructions(idf: IDF):
    layer_r: dict[str, float] = {}
    for m in idf.all("Material"):
        thickness, k = to_float(m.get(2)), to_float(m.get(3))
        if thickness is not None and k:
            layer_r[m.name.upper()] = thickness / k
    for m in idf.all("Material:NoMass"):
        r = to_float(m.get(2))
        if r is not None:
            layer_r[m.name.upper()] = r
    for m in idf.all("Material:AirGap"):
        r = to_float(m.get(1))
        if r is not None:
            layer_r[m.name.upper()] = r
    for m in idf.all("Material:InfraredTransparent"):
        layer_r[m.name.upper()] = 0.0

    simple = {}
    for g in idf.all("WindowMaterial:SimpleGlazingSystem"):
        u, shgc = to_float(g.get(1)), to_float(g.get(2))
        if u is not None and shgc is not None:
            simple[g.name.upper()] = GlazingProps(u, shgc, to_float(g.get(3)), "SimpleGlazingSystem in IDF")

    opaque_r: dict[str, float] = {}
    missing: dict[str, list[str]] = {}
    glazing: dict[str, GlazingProps] = {}
    for c in idf.all("Construction"):
        layers = [f for f in c.fields[1:] if f]
        key = c.name.upper()
        if len(layers) == 1 and layers[0].upper() in simple:
            glazing[key] = simple[layers[0].upper()]
            continue
        unresolved = [name for name in layers if name.upper() not in layer_r]
        if unresolved:
            missing[key] = unresolved
        opaque_r[key] = sum(layer_r.get(name.upper(), 0.0) for name in layers)
    return opaque_r, missing, glazing


def assembly_u(layers_r: float, kind: str) -> float:
    """Assembly U-factor (W/m2K) per ISO 6946, including inside and outside air films."""
    rsi = {"wall": RSI_HORIZONTAL, "roof": RSI_UPWARD, "floor": RSI_DOWNWARD}[kind]
    return 1.0 / (rsi + layers_r + RSE)
