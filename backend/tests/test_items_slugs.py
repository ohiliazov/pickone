from __future__ import annotations

import itertools

import pytest

from pickone.items.slugs import slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Carbonara", "carbonara"),
        ("Fitting bed sheets", "fitting-bed-sheets"),
        ("  Extra   spaces  ", "extra-spaces"),
        ("café", "cafe"),
        ("300 W FTP", "300-w-ftp"),
        ("Hello, World!", "hello-world"),
        ("---leading and trailing---", "leading-and-trailing"),
        ("Cats vs Dogs", "cats-versus-dogs"),
        ("vs code", "vs-code"),
        ("versus already", "versus-already"),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_truncates_cleanly_when_the_cut_lands_on_a_boundary() -> None:
    slug = slugify("word " * 20)
    assert slug == "-".join(["word"] * 13)
    assert len(slug) == 64


def test_slugify_backs_up_to_the_previous_word_when_the_cut_lands_mid_word() -> None:
    slug = slugify("supercalifragilisticexpialidocious " * 3)
    assert len(slug) <= 64
    assert (
        slug
        == "supercalifragilisticexpialidocious-supercalifragilisticexpialidocious"[:64].rsplit(
            "-", 1
        )[0]
    )


def test_slugify_never_exceeds_64_characters() -> None:
    assert len(slugify("a" * 200)) <= 64


WORDS = ["cats", "dogs", "vs", "versus", "pizza", "carbonara", "300", "w", "ftp", "and"]


def test_slugify_never_produces_a_slug_parseable_as_a_comparison() -> None:
    for length in (2, 3, 4):
        for combo in itertools.permutations(WORDS, length):
            text = " ".join(combo)
            assert "-vs-" not in slugify(text)
