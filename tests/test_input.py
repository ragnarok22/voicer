import pytest

from main import read_text


def test_read_text_joins_lines_until_empty_input(monkeypatch) -> None:
    lines = iter(["First line", "Second line", ""])
    monkeypatch.setattr("builtins.input", lambda: next(lines))

    assert read_text() == "First line\nSecond line"


def test_read_text_strips_outer_whitespace(monkeypatch) -> None:
    lines = iter(["  Hello  ", ""])
    monkeypatch.setattr("builtins.input", lambda: next(lines))

    assert read_text() == "Hello"


def test_read_text_exits_when_no_text_is_provided(monkeypatch) -> None:
    lines = iter([""])
    monkeypatch.setattr("builtins.input", lambda: next(lines))

    with pytest.raises(SystemExit) as exc_info:
        read_text()

    assert str(exc_info.value) == "No text provided."
