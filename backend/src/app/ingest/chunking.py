"""Split sections into cited chunks (record 0008, decision 6).

Chunks follow the document's structure: text from different pages or headings is never joined, so
a chunk's location is exact. Inside one page or heading, whole paragraphs are packed up to
`target_chars`; a paragraph that is too long is split at sentences, and a sentence that is too long
at a fixed width. Each chunk repeats the last paragraphs of the one before it, up to
`overlap_chars`, so an answer that straddles a boundary is whole in at least one of them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import groupby

from app.ingest.types import Chunk, Section

DASH = "\u2013"
SENTENCE = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH = re.compile(r"\n{2,}")


@dataclass(slots=True)
class _Unit:
    text: str
    section: Section


@dataclass(slots=True)
class _Pending:
    units: list[_Unit] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(len(u.text) for u in self.units) + 2 * max(0, len(self.units) - 1)


def _slices(text: str, width: int) -> list[str]:
    return [text[i : i + width] for i in range(0, len(text), width)]


def _units(section: Section, target: int) -> list[_Unit]:
    pieces: list[str] = []
    for paragraph in PARAGRAPH.split(section.text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= target:
            pieces.append(paragraph)
            continue
        for sentence in SENTENCE.split(paragraph):
            pieces.extend([sentence] if len(sentence) <= target else _slices(sentence, target))
    return [_Unit(p, section) for p in pieces]


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def locate(sections: list[Section]) -> str:
    first = sections[0]
    starts = [s.start for s in sections if s.start is not None]
    if starts:
        ends = [s.end for s in sections if s.end is not None]
        return f"{_clock(min(starts))}{DASH}{_clock(max(ends or starts))}"
    if first.page is not None:
        return f"p. {first.page}"
    if first.heading_path:
        return " > ".join(first.heading_path)
    lines = [s.lines for s in sections if s.lines is not None]
    if lines:
        low, high = min(a for a, _ in lines), max(b for _, b in lines)
        return f"line {low}" if low == high else f"lines {low}{DASH}{high}"
    return "document"


def _emit(pending: _Pending, position: int) -> Chunk:
    text = "\n\n".join(u.text for u in pending.units)
    distinct = list({id(u.section): u.section for u in pending.units}.values())
    return Chunk(position=position, text=text, location=locate(distinct))


def chunk(
    sections: list[Section], target_chars: int = 1_600, overlap_chars: int = 200
) -> list[Chunk]:
    if target_chars < 100 or not 0 <= overlap_chars < target_chars // 2:
        raise ValueError("overlap must be under half the target, and the target at least 100.")
    out: list[Chunk] = []
    for _, run in groupby(sections, key=lambda s: s.group):
        units = [u for section in run for u in _units(section, target_chars)]
        pending = _Pending()
        fresh = 0  # units in `pending` that are not carried over from the last chunk
        for unit in units:
            if pending.units and pending.size + 2 + len(unit.text) > target_chars:
                out.append(_emit(pending, len(out)))
                carried: list[_Unit] = []
                total = 0
                for old in reversed(pending.units):
                    if total + len(old.text) > overlap_chars:
                        break
                    carried.insert(0, old)
                    total += len(old.text)
                pending = _Pending(carried)
                fresh = 0
            pending.units.append(unit)
            fresh += 1
        if fresh:
            out.append(_emit(pending, len(out)))
    return out
