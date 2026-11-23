"""Check an envelope model against the ECSBC 2024 prescriptive limits."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import limits as L
from .geometry import facade, is_north_facing
from .idf import IDF
from .model import EnvelopeModel, GlazingProps, assembly_u, load_envelope

PASS, FAIL, NOT_EVALUATED = "PASS", "FAIL", "NOT EVALUATED"
FENESTRATION_TYPES = {"window", "glassdoor"}


@dataclass
class Result:
    check: str
    item: str
    value: float | None
    limit: float | None
    status: str
    reference: str
    note: str = ""


@dataclass
class Report:
    zone: str
    level: str
    building_type: str
    latitude: float | None
    results: list[Result]
    areas: dict[str, float]
    facade_wwr: dict[str, tuple[float, float]]  # facade -> (window area, gross wall area)
    warnings: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {PASS: 0, FAIL: 0, NOT_EVALUATED: 0}
        for r in self.results:
            out[r.status] = out.get(r.status, 0) + 1
        return out

    @property
    def overall(self) -> str:
        c = self.counts
        if c[FAIL]:
            return FAIL
        if c[NOT_EVALUATED]:
            return "INCOMPLETE"
        return PASS


def _status(value: float, limit: float, at_most: bool = True) -> str:
    ok = value <= limit + 1e-9 if at_most else value >= limit - 1e-9
    return PASS if ok else FAIL


def check_idf(idf: IDF, **kwargs) -> Report:
    return check_model(load_envelope(idf), **kwargs)


def check_model(
    model: EnvelopeModel,
    zone: str,
    level: str = "ecsbc",
    building_type: str = "default",
    latitude: float | None = None,
    glazing_overrides: dict[str, GlazingProps] | None = None,
    north_half_angle: float = 45.0,
) -> Report:
    L._check(zone, level)
    results: list[Result] = []
    warnings = list(model.warnings)
    lat = latitude if latitude is not None else model.latitude

    exterior = [s for s in model.surfaces if s.is_exterior]
    walls = [s for s in exterior if s.kind == "wall"]
    roofs = [s for s in exterior if s.kind == "roof"]
    if any(s.kind == "floor" for s in exterior):
        warnings.append("Exposed floors found; ECSBC envelope tables do not cover them, so they were not checked.")

    # Opaque assemblies, one result per construction
    for kind, group, limit, table in (
        ("wall", walls, L.wall_u_limit(zone, level, building_type), L.TABLE_REF[("wall", level)]),
        ("roof", roofs, L.roof_u_limit(zone, level, building_type), L.TABLE_REF[("roof", level)]),
    ):
        area_by_cons: dict[str, float] = defaultdict(float)
        for s in group:
            area_by_cons[s.construction] += s.area
        for cons, area in sorted(area_by_cons.items()):
            key = cons.upper()
            if key not in model.opaque_r:
                results.append(Result(f"{kind.title()} U-factor", cons, None, limit, NOT_EVALUATED, table,
                                      "construction not found in the IDF"))
                continue
            u = assembly_u(model.opaque_r[key], kind)
            status = _status(u, limit)
            note = f"{area:.1f} m2"
            if key in model.missing_layers:
                status = NOT_EVALUATED
                note += "; unknown layers: " + ", ".join(model.missing_layers[key])
            elif status == FAIL:
                extra_r = 1.0 / limit - 1.0 / u
                note += f"; add R ≥ {extra_r:.2f} m2K/W of insulation to comply"
            results.append(Result(f"{kind.title()} U-factor", cons, u, limit, status, table, note))

    # Fenestration
    surfaces_by_name = {s.name.upper(): s for s in exterior}
    vertical, skylights = [], []
    for w in model.windows:
        if w.fenestration_type.lower() not in FENESTRATION_TYPES:
            continue
        parent = surfaces_by_name.get(w.parent.upper())
        if parent is None:
            continue
        (skylights if parent.kind == "roof" else vertical).append(w)

    wall_area = sum(s.area for s in walls)
    window_area = sum(w.area for w in vertical)
    roof_area = sum(s.area for s in roofs)
    skylight_area = sum(w.area for w in skylights)

    if wall_area > 0:
        wwr = window_area / wall_area
        results.append(Result("Window-to-wall ratio", "whole building", wwr, L.MAX_WWR, _status(wwr, L.MAX_WWR),
                              L.TABLE_REF[("wwr", None)], f"{window_area:.1f} of {wall_area:.1f} m2"))
    if roof_area > 0:
        srr = skylight_area / roof_area
        results.append(Result("Skylight-to-roof ratio", "whole building", srr, L.MAX_SRR, _status(srr, L.MAX_SRR),
                              L.TABLE_REF[("srr", None)], f"{skylight_area:.1f} of {roof_area:.1f} m2"))

    facade_wwr: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for s in walls:
        facade_wwr[facade(s.geometry.azimuth)][1] += s.area
    for w in vertical:
        facade_wwr[facade(w.geometry.azimuth)][0] += w.area

    overrides = {k.upper(): v for k, v in (glazing_overrides or {}).items()}

    def props(cons: str) -> GlazingProps | None:
        return overrides.get(cons.upper()) or model.glazing.get(cons.upper())

    window_table = L.TABLE_REF[("window", level)]
    u_limit = L.window_u_limit(zone, level)
    if lat is None:
        warnings.append("Latitude unknown (no Site:Location and no --latitude): north SHGC uses the stricter "
                        "below-15°N limit.")
    lat_for_shgc = lat if lat is not None else 0.0

    by_cons: dict[str, list] = defaultdict(list)
    for w in vertical:
        by_cons[w.construction].append(w)
    for cons, group in sorted(by_cons.items()):
        p = props(cons)
        area = sum(w.area for w in group)
        if p is None:
            note = "no U/SHGC in IDF for a layered glazing build-up; supply rated values with --glazing"
            results.append(Result("Window U-factor", cons, None, u_limit, NOT_EVALUATED, window_table, note))
            results.append(Result("Window SHGC", cons, None, None, NOT_EVALUATED, window_table, note))
            continue
        src = f"{area:.1f} m2; values from {p.source}"
        results.append(Result("Window U-factor", cons, p.u, u_limit, _status(p.u, u_limit), window_table, src))
        for north in (False, True):
            sub = [w for w in group if is_north_facing(w.geometry.azimuth, north_half_angle) == north]
            if not sub:
                continue
            lim = L.window_shgc_limit(zone, level, north, lat_for_shgc)
            facades = sorted({facade(w.geometry.azimuth) for w in sub})
            label = f"{cons} ({'north' if north else 'non-north'}: {', '.join(facades)})"
            results.append(Result("Window SHGC", label, p.shgc, lim, _status(p.shgc, lim), window_table,
                                  f"{sum(w.area for w in sub):.1f} m2"))
        if p.vlt is not None:
            results.append(Result("Window VLT (minimum)", cons, p.vlt, L.MIN_VLT,
                                  _status(p.vlt, L.MIN_VLT, at_most=False), L.TABLE_REF[("vlt", None)]))

    sky_cons: dict[str, list] = defaultdict(list)
    for w in skylights:
        sky_cons[w.construction].append(w)
    sky_table = L.TABLE_REF[("skylight", None)]
    for cons, group in sorted(sky_cons.items()):
        p = props(cons)
        if p is None:
            results.append(Result("Skylight U-factor", cons, None, L.SKYLIGHT_MAX_U, NOT_EVALUATED, sky_table,
                                  "supply rated values with --glazing"))
            continue
        results.append(Result("Skylight U-factor", cons, p.u, L.SKYLIGHT_MAX_U, _status(p.u, L.SKYLIGHT_MAX_U),
                              sky_table))
        results.append(Result("Skylight SHGC", cons, p.shgc, L.SKYLIGHT_MAX_SHGC,
                              _status(p.shgc, L.SKYLIGHT_MAX_SHGC), sky_table))

    areas = {
        "gross_wall_area_m2": wall_area,
        "vertical_fenestration_area_m2": window_area,
        "roof_area_m2": roof_area,
        "skylight_area_m2": skylight_area,
    }
    return Report(zone, level, building_type, lat, results, areas,
                  {k: (v[0], v[1]) for k, v in sorted(facade_wwr.items())}, warnings)
