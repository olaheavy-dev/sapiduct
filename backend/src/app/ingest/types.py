"""What a parser hands to the chunker, and what the chunker hands to the index (record 0008)."""

from __future__ import annotations

from dataclasses import dataclass

KINDS = ("pdf", "docx", "md", "txt", "html", "vtt")


class ParseError(Exception):
    """A document that cannot be read. The message is safe to store and show: it never carries
    file content, a path or a library's own error text."""


@dataclass(frozen=True, slots=True)
class Limits:
    """Ceilings on what one document may expand to (record 0009)."""

    max_pages: int = 1_000
    max_chars: int = 5_000_000
    max_uncompressed_bytes: int = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Section:
    """A run of text with where it came from. Only one kind of location is set per format."""

    text: str
    heading_path: tuple[str, ...] = ()
    page: int | None = None
    start: float | None = None  # seconds, for transcripts
    end: float | None = None
    lines: tuple[int, int] | None = None  # first and last line, for plain text

    @property
    def group(self) -> tuple[tuple[str, ...], int | None]:
        """Sections merge into one chunk only within the same page and heading."""
        return (self.heading_path, self.page)


@dataclass(frozen=True, slots=True)
class Chunk:
    position: int
    text: str
    location: str
