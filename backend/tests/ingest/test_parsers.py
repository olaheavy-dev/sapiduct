"""Parsers (record 0008, decision 5): each format's text and location, and hostile input."""

from __future__ import annotations

import os

import pytest

from app.ingest.parsers import parse
from app.ingest.types import KINDS, Limits, ParseError
from tests.ingest import samples


def test_every_supported_kind_has_a_parser() -> None:
    assert set(KINDS) == {"pdf", "docx", "md", "txt", "html", "vtt"}


def test_pdf_pages_keep_their_numbers_and_blank_pages_are_dropped() -> None:
    sections = parse("pdf", samples.pdf(["First page text", "", "Third page text"]))
    assert [(s.page, s.text) for s in sections] == [(1, "First page text"), (3, "Third page text")]


def test_a_pdf_without_a_text_layer_fails_with_a_stated_reason() -> None:
    with pytest.raises(ParseError, match="no text layer"):
        parse("pdf", samples.pdf(["", ""]))


def test_a_password_protected_pdf_is_refused_with_that_reason() -> None:
    with pytest.raises(ParseError, match="password protected"):
        parse("pdf", samples.encrypted_pdf())


def test_a_corrupt_pdf_fails_with_a_safe_message() -> None:
    corrupt = samples.pdf(["secret words"])[:80] + os.urandom(200)
    with pytest.raises(ParseError) as caught:
        parse("pdf", corrupt)
    assert "secret" not in str(caught.value)


def test_random_bytes_are_not_a_pdf() -> None:
    with pytest.raises(ParseError):
        parse("pdf", os.urandom(1000))


def test_a_pdf_over_the_page_limit_is_refused() -> None:
    with pytest.raises(ParseError, match="more than 2 pages"):
        parse("pdf", samples.pdf(["a", "b", "c"]), Limits(max_pages=2))


def test_text_over_the_character_limit_is_refused() -> None:
    with pytest.raises(ParseError, match="more text than the limit"):
        parse("txt", b"word " * 100, Limits(max_chars=100))


def test_word_headings_become_the_heading_path_and_tables_become_rows() -> None:
    sections = parse("docx", samples.docx())
    assert [(s.heading_path, s.text) for s in sections] == [
        (("Thermodynamics",), "Energy is conserved."),
        (("Thermodynamics", "Entropy"), "Entropy never decreases in an isolated system."),
        (("Thermodynamics", "Entropy"), "Law | Statement\nSecond | Entropy rises"),
        (("Heat engines",), "No engine is perfectly efficient."),
    ]


def test_a_word_file_that_expands_past_the_limit_is_refused_before_unpacking() -> None:
    bomb = samples.zip_bomb(8)
    assert len(bomb) < 100_000  # tiny on disk, large when unpacked
    with pytest.raises(ParseError, match="expands past"):
        parse("docx", bomb, Limits(max_uncompressed_bytes=1024 * 1024))


def test_a_file_that_is_not_a_word_file_fails_safely() -> None:
    with pytest.raises(ParseError):
        parse("docx", b"not a zip at all")


def test_markdown_headings_nest_and_code_fences_hide_fake_headings() -> None:
    sections = parse("md", samples.MARKDOWN.encode())
    paths = [s.heading_path for s in sections]
    assert paths == [
        (),
        ("Physics",),
        ("Physics", "Entropy"),
        ("Physics", "Heat"),
        ("Chemistry",),
    ]
    assert "# not a heading, it is code" in sections[2].text
    assert sections[2].lines is not None


def test_plain_text_splits_on_blank_lines_and_records_line_numbers() -> None:
    sections = parse("txt", samples.TEXT.encode())
    assert [(s.text.splitlines()[0], s.lines) for s in sections] == [
        ("First paragraph line one.", (1, 2)),
        ("Second paragraph.", (4, 4)),
        ("Third paragraph.", (7, 7)),
    ]


def test_html_keeps_headings_and_drops_scripts_styles_and_navigation() -> None:
    sections = parse("html", samples.HTML.encode())
    text = " ".join(s.text for s in sections)
    assert "alert" not in text
    assert "color:red" not in text
    assert "Cookies" not in text
    assert "Overview & scope." in text
    assert [s.heading_path for s in sections] == [
        ("Physics",),
        ("Physics", "Entropy"),
        ("Chemistry",),
    ]


def test_html_with_broken_markup_still_yields_text() -> None:
    sections = parse("html", b"<p>one<div>two<h2>Head<p>three</b></i>")
    assert "one" in sections[0].text
    assert any(s.heading_path == ("Head",) for s in sections)


def test_vtt_cues_carry_timestamps() -> None:
    sections = parse("vtt", samples.VTT.encode())
    assert [(s.start, s.end) for s in sections] == [(1.0, 4.0), (4.5, 9.0), (70.0, 74.0)]
    assert sections[0].text == "Welcome to the lecture on entropy."


def test_a_broken_transcript_fails_safely() -> None:
    with pytest.raises(ParseError):
        parse("vtt", b"this is not a transcript")


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ParseError, match="not supported"):
        parse("exe", b"MZ")


@pytest.mark.parametrize("kind", ["md", "txt", "html", "vtt"])
def test_empty_files_fail_with_a_reason(kind: str) -> None:
    with pytest.raises(ParseError):
        parse(kind, b"   \n\n  ")


def test_a_literal_trailing_hash_belongs_to_the_heading() -> None:
    sections = parse("md", b"# C#\nA programming language.\n\n## Notes ##\nClosed heading.")
    assert [s.heading_path for s in sections] == [("C#",), ("C#", "Notes")]


@pytest.mark.parametrize(
    ("opening", "inner_fence"),
    [("~~~python", "```"), ("````", "```"), ("```", "~~~")],
)
def test_a_code_block_is_closed_only_by_a_matching_fence(opening: str, inner_fence: str) -> None:
    source = f"# Real\n\n{opening}\n{inner_fence}\n# this is code\n{opening[0] * 4}\n\nafter\n"
    sections = parse("md", source.encode())
    assert [s.heading_path for s in sections] == [("Real",)]
    assert "# this is code" in sections[0].text
