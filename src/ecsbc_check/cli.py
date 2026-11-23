"""Command line: ecsbc-check MODEL.idf --zone composite [options]."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import limits as L
from .checker import FAIL, check_idf
from .idf import IDF
from .model import GlazingProps
from .report import to_csv, to_json, to_markdown


def load_glazing(path: str) -> dict[str, GlazingProps]:
    """Rated glazing values per construction, from JSON or CSV.

    JSON: {"Construction name": {"u": 1.8, "shgc": 0.24, "vlt": 0.45}}
    CSV:  construction,u,shgc,vlt
    """
    p = Path(path)
    source = f"rated values ({p.name})"
    out: dict[str, GlazingProps] = {}
    if p.suffix.lower() == ".json":
        for name, v in json.loads(p.read_text(encoding="utf-8")).items():
            out[name] = GlazingProps(float(v["u"]), float(v["shgc"]), _opt(v.get("vlt")), source)
    else:
        with p.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out[row["construction"]] = GlazingProps(float(row["u"]), float(row["shgc"]),
                                                        _opt(row.get("vlt")), source)
    return out


def _opt(value) -> float | None:
    return None if value in (None, "") else float(value)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="ecsbc-check",
        description="Check a DesignBuilder / EnergyPlus IDF envelope against ECSBC 2024 prescriptive limits.",
    )
    ap.add_argument("idf", help="EnergyPlus .idf file (DesignBuilder: File > Export > Export EnergyPlus IDF file)")
    ap.add_argument("--zone", required=True, choices=L.ZONES, help="climate zone of the site")
    ap.add_argument("--level", default="ecsbc", choices=L.LEVELS, help="compliance level (default: ecsbc)")
    ap.add_argument("--building-type", default="default", choices=L.BUILDING_TYPES,
                    help="building category for the roof and wall tables (default: default)")
    ap.add_argument("--latitude", type=float, help="site latitude in degrees N (overrides Site:Location)")
    ap.add_argument("--glazing", help="JSON or CSV of rated window U, SHGC and VLT per construction")
    ap.add_argument("--north-angle", type=float, default=45.0,
                    help="windows within this many degrees of true north count as north-facing (default 45)")
    ap.add_argument("--format", default="md", choices=("md", "csv", "json"), help="output format")
    ap.add_argument("-o", "--output", help="write the report to this file instead of the screen")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    idf = IDF.from_file(args.idf)
    report = check_idf(
        idf,
        zone=args.zone,
        level=args.level,
        building_type=args.building_type,
        latitude=args.latitude,
        glazing_overrides=load_glazing(args.glazing) if args.glazing else None,
        north_half_angle=args.north_angle,
    )
    if args.format == "csv":
        text = to_csv(report)
    elif args.format == "json":
        text = to_json(report)
    else:
        text = to_markdown(report, Path(args.idf).name)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 1 if report.overall == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
