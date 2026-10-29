"""Conversation title derivation."""

from lucid.application.titles import FALLBACK_TITLE, MAX_TITLE_CODE_POINTS, derive_title


def test_empty_message_falls_back() -> None:
    assert derive_title("") == FALLBACK_TITLE
    assert derive_title("   \n\t ") == FALLBACK_TITLE


def test_short_message_is_used_verbatim() -> None:
    assert derive_title("Explain SSE vs WebSockets") == "Explain SSE vs WebSockets"


def test_whitespace_is_collapsed() -> None:
    assert derive_title("  hello    world \n again ") == "hello world again"


def test_control_characters_are_stripped() -> None:
    assert derive_title("hello\x00\x07world") == "helloworld"


def test_message_exactly_at_the_limit_is_unchanged() -> None:
    text = "a" * MAX_TITLE_CODE_POINTS

    assert derive_title(text) == text


def test_long_message_cuts_at_word_boundary() -> None:
    text = "a" * 70 + " " + "b" * 20

    assert derive_title(text) == "a" * 70


def test_long_message_without_spaces_is_hard_cut() -> None:
    text = "a" * 200

    assert derive_title(text) == "a" * MAX_TITLE_CODE_POINTS


def test_trailing_punctuation_is_trimmed_after_cut() -> None:
    text = "word " * 20 + ","

    title = derive_title(text)

    assert len(title) <= MAX_TITLE_CODE_POINTS
    assert not title.endswith(" ")
    assert not title.endswith(",")


def test_emoji_counted_as_code_points_not_bytes() -> None:
    text = "\U0001f600" * 40

    assert derive_title(text) == text


def test_titles_never_exceed_the_limit() -> None:
    for length in (79, 80, 81, 120, 5000):
        title = derive_title("x" * length)
        assert 0 < len(title) <= MAX_TITLE_CODE_POINTS
