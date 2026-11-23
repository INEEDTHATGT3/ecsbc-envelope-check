import json
from pathlib import Path

import pytest

from ecsbc_check import IDF, GlazingProps, check_idf, load_envelope
from ecsbc_check import limits as L
from ecsbc_check.cli import main
from ecsbc_check.geometry import facade, is_north_facing, orientation
from ecsbc_check.idf import parse_idf_text
from ecsbc_check.model import assembly_u, extract_vertices

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "small_office_noida.idf"

# Hand calculations for the example model (ISO 6946 films: Rsi 0.13 wall / 0.10 roof, Rse 0.04)
WALL_R_LAYERS = 2 * 0.012 / 0.72 + 0.075 / 0.034 + 0.23 / 0.81
ROOF_R_LAYERS = 0.05 / 0.72 + 0.05 / 0.023 + 0.15 / 1.58 + 0.012 / 0.72
WALL_U = 1 / (0.13 + WALL_R_LAYERS + 0.04)  # 0.3713
ROOF_U = 1 / (0.10 + ROOF_R_LAYERS + 0.04)  # 0.4008


@pytest.fixture(scope="module")
def report():
    return check_idf(IDF.from_file(EXAMPLE), zone="composite")


def by_check(report, check, item_start=""):
    return [r for r in report.results if r.check == check and r.item.startswith(item_start)]


# ---------- IDF parsing ----------

def test_parser_handles_comments_and_case():
    objs = parse_idf_text("Version, 9.4; ! comment ; with semicolon\nMATERIAL ,A,Rough,0.1,1.0 ; !- trailing")
    assert [o.cls for o in objs] == ["Version", "MATERIAL"]
    assert objs[1].fields == ["A", "Rough", "0.1", "1.0"]
    idf = IDF(objs)
    assert idf.by_name("Material")["A"].get(3) == "1.0"


def test_extract_vertices_with_count_and_autocalculate():
    with_count = ["n", "Wall", "c", "z", "Outdoors", "", "SunExposed", "WindExposed", "0.5", "3",
                  "0", "0", "0", "1", "0", "0", "1", "1", "0"]
    verts, k = extract_vertices(with_count, 9)
    assert len(verts) == 3 and k == 9
    blank_count = with_count[:9] + ["autocalculate"] + with_count[10:]
    verts2, _ = extract_vertices(blank_count, 9)
    assert verts2 == verts


# ---------- geometry ----------

def test_orientation_of_example_walls():
    south = orientation([(0, 0, 3.5), (0, 0, 0), (20, 0, 0), (20, 0, 3.5)])
    assert south.area == pytest.approx(70.0)
    assert south.azimuth == pytest.approx(180.0)
    assert south.tilt == pytest.approx(90.0)
    roof = orientation([(0, 10, 3.5), (0, 0, 3.5), (20, 0, 3.5), (20, 10, 3.5)])
    assert roof.tilt == pytest.approx(0.0)


def test_north_axis_rotates_azimuth_and_clockwise_flips_normal():
    south = [(0, 0, 3.5), (0, 0, 0), (20, 0, 0), (20, 0, 3.5)]
    assert orientation(south, north_axis_deg=30).azimuth == pytest.approx(210.0)
    assert orientation(south, clockwise=True).azimuth == pytest.approx(0.0)


def test_facade_and_north_sector():
    assert facade(10) == "North" and facade(100) == "East" and facade(200) == "South" and facade(300) == "West"
    assert is_north_facing(350) and is_north_facing(44) and not is_north_facing(46)


# ---------- limits ----------

def test_limit_tables():
    assert L.wall_u_limit("composite") == 0.40
    assert L.wall_u_limit("temperate", "ecsbc", "school_small") == 1.00
    assert L.wall_u_limit("cold", "ecsbc_plus") == 0.22
    assert L.roof_u_limit("cold") == 0.20
    assert L.roof_u_limit("composite", "ecsbc", "assembly_hospitality_large") == 0.20
    assert L.roof_u_limit("warm_humid", "super") == 0.18
    assert L.window_u_limit("temperate") == 3.00
    assert L.window_shgc_limit("composite", "ecsbc", north=True, latitude=28.6) == 0.50
    assert L.window_shgc_limit("composite", "ecsbc", north=True, latitude=12.9) == 0.25
    assert L.window_shgc_limit("hot_dry", "super", north=False, latitude=26) == 0.20
    with pytest.raises(ValueError):
        L.wall_u_limit("tropical")


# ---------- U-factors ----------

def test_assembly_u_values_match_hand_calculation():
    model = load_envelope(IDF.from_file(EXAMPLE))
    wall_r = model.opaque_r["EXT WALL - BRICK + 75MM XPS"]
    roof_r = model.opaque_r["FLAT ROOF - RCC + 50MM PUF"]
    assert wall_r == pytest.approx(WALL_R_LAYERS)
    assert assembly_u(wall_r, "wall") == pytest.approx(WALL_U)
    assert assembly_u(roof_r, "roof") == pytest.approx(ROOF_U)
    assert WALL_U == pytest.approx(0.3713, abs=1e-4)
    assert ROOF_U == pytest.approx(0.4008, abs=1e-4)


# ---------- full check on the example ----------

def test_example_results(report):
    (wall,) = by_check(report, "Wall U-factor")
    assert wall.status == "PASS" and wall.value == pytest.approx(WALL_U)

    (roof,) = by_check(report, "Roof U-factor")
    assert roof.status == "FAIL" and roof.limit == 0.26
    extra_r = 1 / 0.26 - 1 / ROOF_U
    assert extra_r == pytest.approx(1.351, abs=1e-3)
    assert "1.35" in roof.note

    (wwr,) = by_check(report, "Window-to-wall ratio")
    assert wwr.value == pytest.approx(39.6 / 210.0) and wwr.status == "PASS"

    (srr,) = by_check(report, "Skylight-to-roof ratio")
    assert srr.value == 0 and srr.status == "PASS"

    shgc = {r.item: r for r in by_check(report, "Window SHGC")}
    non_north = next(r for k, r in shgc.items() if "non-north" in k)
    north = next(r for k, r in shgc.items() if "(north" in k)
    assert non_north.status == "FAIL" and non_north.limit == 0.25
    assert "East, South, West" in non_north.item
    assert north.status == "PASS" and north.limit == 0.50

    assert by_check(report, "Window U-factor")[0].status == "PASS"
    assert by_check(report, "Window VLT (minimum)")[0].status == "PASS"
    assert report.counts == {"PASS": 6, "FAIL": 2, "NOT EVALUATED": 0}
    assert report.overall == "FAIL"
    assert report.latitude == pytest.approx(28.57)


def test_facade_wwr(report):
    win, wall = report.facade_wwr["South"]
    assert win == pytest.approx(14.4) and wall == pytest.approx(70.0)


def test_glazing_override_fixes_shgc():
    better = {"DGU low-e window": GlazingProps(u=1.8, shgc=0.24, vlt=0.40, source="test")}
    rep = check_idf(IDF.from_file(EXAMPLE), zone="composite", glazing_overrides=better)
    assert all(r.status == "PASS" for r in rep.results if r.check.startswith("Window"))


def test_space_name_field_and_missing_layer():
    text = """
    Material, M, Rough, 0.2, 1.0, 1000, 1000;
    Construction, W, M, Unknown layer;
    BuildingSurface:Detailed, S, Wall, W, Z1, Space1, Outdoors, , SunExposed, WindExposed, 0.5, 4,
        0,0,3, 0,0,0, 10,0,0, 10,0,3;
    """
    rep = check_idf(IDF.from_text(text), zone="hot_dry", latitude=26.9)
    (wall,) = by_check(rep, "Wall U-factor")
    assert wall.status == "NOT EVALUATED" and "Unknown layer" in wall.note
    assert rep.areas["gross_wall_area_m2"] == pytest.approx(30.0)


def test_zone_multiplier_scales_area():
    text = """
    Zone, Z1, 0, 0, 0, 0, 1, 3;
    Material, M, Rough, 0.2, 1.0, 1000, 1000;
    Construction, W, M;
    BuildingSurface:Detailed, S, Wall, W, Z1, Outdoors, , SunExposed, WindExposed, 0.5, 4,
        0,0,3, 0,0,0, 10,0,0, 10,0,3;
    """
    rep = check_idf(IDF.from_text(text), zone="composite", latitude=28)
    assert rep.areas["gross_wall_area_m2"] == pytest.approx(90.0)


# ---------- CLI ----------

def test_cli_writes_reports(tmp_path, capsys):
    assert main([str(EXAMPLE), "--zone", "composite"]) == 1  # example has 2 failures
    md = capsys.readouterr().out
    assert "Overall: FAIL" in md and "ECSBC 2024 Table 5.3" in md

    out = tmp_path / "r.json"
    main([str(EXAMPLE), "--zone", "composite", "--format", "json", "-o", str(out)])
    data = json.loads(out.read_text())
    assert data["counts"]["FAIL"] == 2

    glazing = tmp_path / "glazing.csv"
    glazing.write_text("construction,u,shgc,vlt\nDGU low-e window,1.8,0.24,0.4\n")
    main([str(EXAMPLE), "--zone", "composite", "--glazing", str(glazing), "--format", "csv",
          "-o", str(tmp_path / "r.csv")])
    assert "rated values (glazing.csv)" in (tmp_path / "r.csv").read_text()
