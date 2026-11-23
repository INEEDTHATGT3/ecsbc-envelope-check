"""Minimal EnergyPlus IDF reader.

Parses the plain-text IDF format that DesignBuilder writes when you use
File > Export > Export EnergyPlus IDF file. No IDD file and no EnergyPlus
install are needed: objects are split on ';', fields on ',', and anything
after '!' on a line is a comment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IDFObject:
    """One IDF object: its class name and its fields (class name excluded)."""

    cls: str
    fields: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.fields[0] if self.fields else ""

    def get(self, index: int, default: str = "") -> str:
        if index < len(self.fields):
            return self.fields[index]
        return default


class IDF:
    """A parsed IDF file, indexed by lower-case class name."""

    def __init__(self, objects: list[IDFObject]):
        self.objects = objects
        self._by_class: dict[str, list[IDFObject]] = defaultdict(list)
        for obj in objects:
            self._by_class[obj.cls.lower()].append(obj)

    def all(self, cls: str) -> list[IDFObject]:
        return list(self._by_class.get(cls.lower(), []))

    def first(self, cls: str) -> IDFObject | None:
        items = self._by_class.get(cls.lower(), [])
        return items[0] if items else None

    def by_name(self, cls: str) -> dict[str, IDFObject]:
        """Objects of one class keyed by upper-case name (IDF names are case-insensitive)."""
        return {obj.name.upper(): obj for obj in self.all(cls)}

    @classmethod
    def from_text(cls, text: str) -> "IDF":
        return cls(parse_idf_text(text))

    @classmethod
    def from_file(cls, path: str | Path) -> "IDF":
        raw = Path(path).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            # DesignBuilder on Windows can write cp1252 (e.g. degree signs in comments)
            text = raw.decode("latin-1")
        return cls.from_text(text)


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cut = line.find("!")
        lines.append(line if cut < 0 else line[:cut])
    return "\n".join(lines)


def parse_idf_text(text: str) -> list[IDFObject]:
    """Return every object in an IDF string, in file order."""
    body = _strip_comments(text)
    objects: list[IDFObject] = []
    for chunk in body.split(";"):
        parts = [p.strip() for p in chunk.split(",")]
        if not parts or not parts[0]:
            continue
        objects.append(IDFObject(cls=parts[0], fields=parts[1:]))
    return objects


def to_float(value: str, default: float | None = None) -> float | None:
    """Parse a numeric IDF field; blank, 'autocalculate' etc. return the default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
