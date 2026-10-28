"""Chunking (record 0008, decision 6): bounds, locations, overlap."""

from __future__ import annotations

from itertools import pairwise

import pytest

from app.ingest.chunking import chunk
from app.ingest.parsers import parse
from app.ingest.types import Section
from tests.ingest import samples


def words(n: int) -> str:
    return " ".join(f"w{i}." for i in range(n))


def test_a_small_document_is_one_chunk_per_page_and_never_joins_pages() -> None:
    chunks = chunk(parse("pdf", samples.pdf(["one", "two", "three"])))
    assert [(c.position, c.location, c.text) for c in chunks] == [
        (0, "p. 1", "one"),
        (1, "p. 2", "two"),
        (2, "p. 3", "three"),
    ]


def test_no_chunk_exceeds_the_target_even_for_one_endless_word() -> None:
    chunks = chunk([Section("x" * 5000, page=1)], target_chars=500, overlap_chars=50)
    assert len(chunks) == 10
    assert max(len(c.text) for c in chunks) <= 500


def test_a_long_paragraph_splits_at_sentences_not_mid_word() -> None:
    chunks = chunk([Section(words(400), page=1)], target_chars=300, overlap_chars=60)
    assert len(chunks) > 5
    assert all(len(c.text) <= 300 for c in chunks)
    assert all(c.text.rstrip().endswith(".") for c in chunks)


def test_consecutive_chunks_share_their_overlap() -> None:
    paragraphs = "\n\n".join(f"Paragraph number {i} with some words in it." for i in range(30))
    chunks = chunk([Section(paragraphs, page=1)], target_chars=400, overlap_chars=100)
    assert len(chunks) > 2
    for before, after in pairwise(chunks):
        last = before.text.split("\n\n")[-1]
        assert last in after.text  # the previous chunk's last paragraph repeats


def test_zero_overlap_repeats_nothing() -> None:
    paragraphs = "\n\n".join(f"Paragraph number {i} with some words in it." for i in range(30))
    chunks = chunk([Section(paragraphs, page=1)], target_chars=400, overlap_chars=0)
    joined = "\n\n".join(c.text for c in chunks)
    assert joined == paragraphs


def test_every_paragraph_is_in_some_chunk() -> None:
    paragraphs = [f"Unique paragraph {i} here." for i in range(50)]
    chunks = chunk([Section("\n\n".join(paragraphs), page=1)], target_chars=300, overlap_chars=60)
    text = "\n".join(c.text for c in chunks)
    assert all(p in text for p in paragraphs)


def test_word_chunks_are_located_by_heading_path() -> None:
    chunks = chunk(parse("docx", samples.docx()))
    assert [c.location for c in chunks] == [
        "Thermodynamics",
        "Thermodynamics > Entropy",
        "Heat engines",
    ]


def test_transcript_cues_merge_and_are_located_by_time_range() -> None:
    chunks = chunk(parse("vtt", samples.VTT.encode()))
    assert len(chunks) == 1
    assert chunks[0].location == "00:00:01\u201300:01:14"


def test_plain_text_is_located_by_lines() -> None:
    chunks = chunk(parse("txt", samples.TEXT.encode()))
    assert [c.location for c in chunks] == ["lines 1\u20137"]


def test_a_single_line_is_located_as_one_line() -> None:
    assert chunk(parse("txt", b"just one line"))[0].location == "line 1"


@pytest.mark.parametrize(("target", "overlap"), [(50, 0), (500, 250), (500, -1)])
def test_unreasonable_settings_are_refused(target: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk([Section("text", page=1)], target_chars=target, overlap_chars=overlap)


def test_positions_are_dense_and_start_at_zero() -> None:
    chunks = chunk(parse("md", samples.MARKDOWN.encode()), target_chars=120, overlap_chars=20)
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_carried_overlap_never_pushes_a_chunk_past_the_target() -> None:
    # 50, 30 and 100 characters with a target of 100: carrying the 30 beside the 100 would make 132.
    section = Section("\n\n".join(["a" * 50, "b" * 30, "c" * 100]), page=1)
    chunks = chunk([section], target_chars=100, overlap_chars=40)
    assert max(len(c.text) for c in chunks) <= 100
    assert "c" * 100 in chunks[-1].text


def test_the_target_holds_for_many_shapes_of_paragraph() -> None:
    import random

    rng = random.Random(7)  # noqa: S311 - a seeded shuffle for a test, not security
    for _ in range(200):
        paragraphs = ["x" * rng.randint(1, 140) for _ in range(rng.randint(1, 12))]
        target = rng.randint(100, 300)
        chunks = chunk(
            [Section("\n\n".join(paragraphs), page=1)], target, rng.randint(0, target // 2 - 1)
        )
        assert all(len(c.text) <= target for c in chunks), (paragraphs, target)
