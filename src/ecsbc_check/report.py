"""Render a Report as Markdown, CSV or JSON."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict

from .checker import Report

ZONE_LABELS = {
    "composite": "Composite",
    "hot_dry": "Hot and dry",
    "warm_humid": "Warm and humid",
    "temperate": "Temperate",
    "cold": "Cold",
}
LEVEL_LABELS = {"ecsbc": "ECSBC", "ecsbc_plus": "ECSBC+", "super": "Super ECSBC"}


def _fmt(value: float | None, check: str) -> str:
    if value is None:
        return "–"
    if "ratio" in check.lower():
        return f"{value * 100:.1f}%"
    return f"{value:.3f}" if value < 10 else f"{value:.1f}"


def to_markdown(report: Report, model_name: str = "") -> str:
    c = report.counts
    lat = f"{report.latitude:.2f}°N" if report.latitude is not None else "unknown"
    out = [
        "# ECSBC 2024 envelope check",
        "",
        f"- Model: {model_name or '(not named)'}",
        f"- Climate zone: {ZONE_LABELS[report.zone]} · Level: {LEVEL_LABELS[report.level]} · "
        f"Building type: {report.building_type} · Latitude: {lat}",
        f"- **Overall: {report.overall}** ({c['PASS']} pass, {c['FAIL']} fail, "
        f"{c['NOT EVALUATED']} not evaluated)",
        "",
        "| Check | Item | Value | Limit | Status | Reference | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report.results:
        out.append(
            f"| {r.check} | {r.item} | {_fmt(r.value, r.check)} | {_fmt(r.limit, r.check)} | "
            f"**{r.status}** | {r.reference} | {r.note} |"
        )
    if report.facade_wwr:
        out += ["", "## Window-to-wall ratio by facade", "", "| Facade | Window m2 | Gross wall m2 | WWR |",
                "|---|---|---|---|"]
        for name, (win, wall) in report.facade_wwr.items():
            ratio = f"{win / wall * 100:.1f}%" if wall else "–"
            out.append(f"| {name} | {win:.1f} | {wall:.1f} | {ratio} |")
    if report.warnings:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in report.warnings]
    out += [
        "",
        "_Prescriptive pre-check only. U-factors use ISO 6946 air films (Rsi 0.13 walls, 0.10 roofs; Rse 0.04) "
        "and ignore thermal bridging. Confirm against the notified ECSBC and any state amendment._",
        "",
    ]
    return "\n".join(out)


def to_csv(report: Report) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["check", "item", "value", "limit", "status", "reference", "note"])
    for r in report.results:
        writer.writerow([r.check, r.item, r.value, r.limit, r.status, r.reference, r.note])
    return buf.getvalue()


def to_json(report: Report) -> str:
    data = {
        "zone": report.zone,
        "level": report.level,
        "building_type": report.building_type,
        "latitude": report.latitude,
        "overall": report.overall,
        "counts": report.counts,
        "areas": report.areas,
        "facade_wwr": {k: {"window_m2": v[0], "gross_wall_m2": v[1]} for k, v in report.facade_wwr.items()},
        "results": [asdict(r) for r in report.results],
        "warnings": report.warnings,
    }
    return json.dumps(data, indent=2)
