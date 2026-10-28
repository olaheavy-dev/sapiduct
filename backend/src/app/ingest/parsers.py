"""Turn an uploaded file's bytes into sections (record 0008, decision 5).

Every parser works on bytes already in memory, opens nothing, fetches nothing and runs no code from
the file. Failures become `ParseError` with a fixed message: a parser library's own error text can
quote the file. These run in the credential-free parser service (decision 4); nothing here knows
about the database or the network.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable, Iterator
from html.parser import HTMLParser

import webvtt
from docx import Document as open_docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.ingest.types import KINDS, Limits, ParseError, Section

# A closing run of hashes counts only after whitespace, so "# C#" is the heading "C#".
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
WORD_HEADING = re.compile(r"^Heading (\d)$")


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _capped(sections: list[Section], limits: Limits) -> list[Section]:
    if sum(len(s.text) for s in sections) > limits.max_chars:
        raise ParseError("The document has more text than the limit allows.")
    kept = [s for s in sections if s.text.strip()]
    if not kept:
        raise ParseError("No readable text was found in this document.")
    return kept


def _push(
    out: list[Section], lines: list[str], path: tuple[str, ...], first: int, last: int
) -> None:
    text = "\n".join(lines).strip()
    if text:
        out.append(Section(text=text, heading_path=path, lines=(first, last)))


def parse_markdown(data: bytes, limits: Limits) -> list[Section]:
    out: list[Section] = []
    path: list[tuple[int, str]] = []
    buffer: list[str] = []
    first = 1
    fence: str | None = None  # the opening fence, while inside a code block
    for number, line in enumerate(_decode(data).split("\n"), start=1):
        marker = FENCE.match(line)
        if fence is None:
            # A backtick fence's info string cannot itself contain a backtick.
            if marker and not (marker.group(1)[0] == "`" and "`" in marker.group(2)):
                fence = marker.group(1)
        elif (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
            and not marker.group(2).strip()
        ):
            fence = None
        match = None if fence is not None or marker else HEADING.match(line)
        if match:
            _push(out, buffer, tuple(t for _, t in path), first, number - 1)
            buffer, first = [], number
            level, title = len(match.group(1)), match.group(2).strip()
            path = [p for p in path if p[0] < level] + [(level, title)]
        else:
            buffer.append(line)
    _push(out, buffer, tuple(t for _, t in path), first, number)
    return _capped(out, limits)


def parse_text(data: bytes, limits: Limits) -> list[Section]:
    out: list[Section] = []
    buffer: list[str] = []
    first = 1
    number = 0
    for number, line in enumerate(_decode(data).split("\n"), start=1):
        if line.strip():
            if not buffer:
                first = number
            buffer.append(line)
        elif buffer:
            out.append(Section("\n".join(buffer), lines=(first, number - 1)))
            buffer = []
    if buffer:
        out.append(Section("\n".join(buffer), lines=(first, number)))
    return _capped(out, limits)


class _Html(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "template", "nav", "head", "svg", "iframe"})
    BLOCK = frozenset(
        {
            "p",
            "div",
            "li",
            "tr",
            "br",
            "section",
            "article",
            "blockquote",
            "pre",
            "ul",
            "ol",
            "table",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[Section] = []
        self.path: list[tuple[int, str]] = []
        self.buffer: list[str] = []
        self.skip_depth = 0
        self.heading_level: int | None = None
        self.heading_text: list[str] = []

    def flush(self) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(self.buffer))
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if text:
            self.sections.append(Section(text, heading_path=tuple(t for _, t in self.path)))
        self.buffer = []

    def close_heading(self) -> None:
        if self.heading_level is None:
            return
        title = " ".join("".join(self.heading_text).split())
        if title:
            level = self.heading_level
            self.path = [p for p in self.path if p[0] < level] + [(level, title)]
        self.heading_level = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif self.skip_depth:
            return
        elif len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self.close_heading()  # a heading that was never closed ends at the next one
            self.flush()
            self.heading_level, self.heading_text = int(tag[1]), []
        elif tag in self.BLOCK:
            self.close_heading()  # ...and at the next block
            self.buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif self.skip_depth:
            return
        elif self.heading_level is not None and tag == f"h{self.heading_level}":
            self.close_heading()
        elif tag in self.BLOCK:
            self.buffer.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        (self.heading_text if self.heading_level is not None else self.buffer).append(data)


def parse_html(data: bytes, limits: Limits) -> list[Section]:
    parser = _Html()
    try:
        parser.feed(_decode(data))
        parser.close()
    except Exception:
        raise ParseError("This HTML file could not be read.") from None
    parser.close_heading()
    parser.flush()
    return _capped(parser.sections, limits)


def _stamp(value: str) -> float:
    hours, minutes, seconds = (
        value.split(":") if value.count(":") == 2 else ("0", *value.split(":"))
    )
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_vtt(data: bytes, limits: Limits) -> list[Section]:
    try:
        cues = webvtt.from_buffer(io.StringIO(_decode(data))).captions
        out = [
            Section(
                " ".join(cue.text.split()),
                start=_stamp(cue.start),
                end=_stamp(cue.end),
            )
            for cue in cues
        ]
    except Exception:
        raise ParseError("This transcript could not be read.") from None
    return _capped(out, limits)


def _check_zip(data: bytes, limits: Limits) -> None:
    """Refuse a Word file that expands past the limit before anything unpacks it."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            total = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile:
        raise ParseError("This Word file could not be read.") from None
    if total > limits.max_uncompressed_bytes:
        raise ParseError("This Word file expands past the size limit.")


def _word_blocks(document: DocxDocument) -> Iterator[Paragraph | Table]:
    yield from document.iter_inner_content()


def parse_docx(data: bytes, limits: Limits) -> list[Section]:
    _check_zip(data, limits)
    try:
        document = open_docx(io.BytesIO(data))
        out: list[Section] = []
        path: list[tuple[int, str]] = []
        for block in _word_blocks(document):
            if isinstance(block, Table):
                rows = [" | ".join(c.text.strip() for c in row.cells) for row in block.rows]
                text = "\n".join(r for r in rows if r.strip(" |"))
            else:
                style = block.style.name if block.style is not None else ""
                heading = WORD_HEADING.match(style or "")
                if heading or style == "Title":
                    level = int(heading.group(1)) if heading else 1
                    title = block.text.strip()
                    if title:
                        path = [p for p in path if p[0] < level] + [(level, title)]
                    continue
                text = block.text
            if text.strip():
                out.append(Section(text.strip(), heading_path=tuple(t for _, t in path)))
    except ParseError:
        raise
    except Exception:
        raise ParseError("This Word file could not be read.") from None
    return _capped(out, limits)


def parse_pdf(data: bytes, limits: Limits) -> list[Section]:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ParseError("This PDF is password protected.")
        count = len(reader.pages)
        if count > limits.max_pages:
            raise ParseError(f"This PDF has more than {limits.max_pages} pages.")
        out = [
            Section((page.extract_text() or "").strip(), page=number)
            for number, page in enumerate(reader.pages, start=1)
        ]
    except ParseError:
        raise
    except (PyPdfError, Exception):
        raise ParseError("This PDF could not be read.") from None
    if not any(s.text for s in out):
        raise ParseError("This PDF has no text layer; scanned pages are not supported yet.")
    return _capped(out, limits)


PARSERS: dict[str, Callable[[bytes, Limits], list[Section]]] = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "md": parse_markdown,
    "txt": parse_text,
    "html": parse_html,
    "vtt": parse_vtt,
}
if set(PARSERS) != set(KINDS):
    raise RuntimeError("every supported kind needs a parser")


def parse(kind: str, data: bytes, limits: Limits | None = None) -> list[Section]:
    parser = PARSERS.get(kind)
    if parser is None:
        raise ParseError("This file type is not supported.")
    return parser(data, limits or Limits())
