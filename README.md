# ecsbc-envelope-check

Check a DesignBuilder or EnergyPlus model's building envelope against India's **Energy Conservation and Sustainable Building Code (ECSBC) 2024** prescriptive limits, straight from the exported `.idf` file.

It answers the first questions a compliance review asks: what is the U-factor of each wall and roof build-up, what is the window-to-wall ratio, and do the windows meet the U-factor and SHGC limits for the climate zone. When an assembly fails, it tells you how much insulation (as an R-value) closes the gap.

## What it checks

| Check | Rule | Source |
|---|---|---|
| Opaque wall U-factor, per construction | limit by climate zone, level and building type | ECSBC 2024 Tables 5.6 to 5.8 |
| Roof U-factor, per construction | limit by climate zone, level and building type | ECSBC 2024 Tables 5.3 to 5-5 |
| Window-to-wall ratio (WWR) | at most 40% | §5.3.3 |
| Window U-factor | limit by climate zone and level | Tables 5.9 to 5.11 |
| Window SHGC, north and non-north | north limit depends on latitude (15°N) | Tables 5.9 to 5.11 |
| Window visible light transmittance | at least 0.27 | §5.3.3 |
| Skylight-to-roof ratio (SRR) | at most 5% | §5.3.4 |
| Skylight U-factor and SHGC | at most 4.25 and 0.35 | Table 5.15 |

Levels: `ecsbc`, `ecsbc_plus`, `super`. Climate zones: `composite`, `hot_dry`, `warm_humid`, `temperate`, `cold`.

## Quick start

```bash
pip install git+https://github.com/INEEDTHATGT3/ecsbc-envelope-check
ecsbc-check examples/small_office_noida.idf --zone composite
```

Getting the IDF out of DesignBuilder: **File > Export > Export EnergyPlus IDF file > Simulation** (needs a licensed copy), or copy the `in.idf` DesignBuilder writes to its EnergyPlus folder before each run.

Options:

```
--zone {composite,hot_dry,warm_humid,temperate,cold}   required
--level {ecsbc,ecsbc_plus,super}                       default: ecsbc
--building-type {default,assembly_hospitality_large,no_star_hotel_small,business_small,school_small}
--latitude 28.6          overrides Site:Location (sets the north SHGC limit)
--glazing rated.json     rated window U / SHGC / VLT per construction (JSON or CSV)
--north-angle 45         windows within this many degrees of true north count as north-facing
--format {md,csv,json}   -o report.md
```

The command exits with code 1 when any check fails, so it can run in a script or CI job.

## Example

`examples/small_office_noida.idf` is a 20 m × 10 m single-zone office in Noida (composite zone) with an insulated brick wall, an RCC roof with 50 mm PUF and double-glazed low-e windows. Result ([full report](examples/small_office_noida_report.md)):

| Check | Value | Limit | Status |
|---|---|---|---|
| Wall U-factor (brick + 75 mm XPS) | 0.371 | 0.40 | PASS |
| Roof U-factor (RCC + 50 mm PUF) | 0.401 | 0.26 | FAIL: add R ≥ 1.35 m²K/W |
| Window-to-wall ratio | 18.9% | 40% | PASS |
| Window SHGC, east/south/west | 0.28 | 0.25 | FAIL |
| Window SHGC, north (28.6°N) | 0.28 | 0.50 | PASS |

An R of 1.35 m²K/W is about 31 mm more PUF (k = 0.023 W/mK), so the roof complies with at least 82 mm of PUF in total.

## How it works

1. **Reads the IDF** without EnergyPlus or an IDD file. It handles comments, the `Space Name` field added in EnergyPlus 22.1, blank or `autocalculate` vertex counts, and the field order of older `FenestrationSurface:Detailed` objects.
2. **Geometry:** each surface's area and outward normal come from Newell's method. Azimuth includes the Building North Axis (and the zone's relative north for relative coordinates). Zone and window multipliers are applied. Surfaces sloped under 60° count as roofs.
3. **U-factors** follow ISO 6946, as ECSBC §5.2.2 requires: layer resistances (thickness / conductivity, or the R of no-mass and air-gap layers) plus surface films Rsi = 0.13 (walls) or 0.10 (roofs) and Rse = 0.04 m²K/W.
4. **Limits** live in `src/ecsbc_check/limits.py`, one dictionary per table, so a state amendment can be added in one place.

## Limitations

- Prescriptive check only. It does not run the Building Envelope Trade-off Method (§5.3.5) or the Whole Building Performance method.
- Thermal bridging, framing and the cool-roof requirement are not assessed.
- Window values come from `WindowMaterial:SimpleGlazingSystem`. ECSBC asks for the **whole-product** U-factor (ISO 15099, frame included), so for layered glazing or framed products pass the manufacturer's rated values with `--glazing`.
- The 0.8 W/m²K wall exception for unconditioned hotels, healthcare and schools, the shading-equivalent-factor credit and the high-sill SHGC exemption are not applied.
- Geometry must use `BuildingSurface:Detailed` and `FenestrationSurface:Detailed`, which is what DesignBuilder exports. Simplified objects such as `Wall:Exterior` are ignored.
- Tested on hand-written IDF files in EnergyPlus 9.4 and 22.1+ syntax. It has not yet been run on a real DesignBuilder export. If yours misbehaves, open an issue with a trimmed file.
- The limits were transcribed from BEE's published ECSBC 2024. Check them against the notified code and your state's rules before relying on a result.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests check the parser, the geometry, every limits table lookup, and the example's U-values against a hand calculation.

## License

MIT
