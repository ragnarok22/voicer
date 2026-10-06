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


def test_read_text_accepts_eof_after_text(monkeypatch) -> None:
    calls = 0

    def read_line():
        nonlocal calls
        calls += 1
        if calls == 1:
            return "Hello"
        raise EOFError

    monkeypatch.setattr("builtins.input", read_line)
    assert read_text() == "Hello"


def test_read_text_empty_eof_is_a_cli_error(monkeypatch) -> None:
    def read_line():
        raise EOFError

    monkeypatch.setattr("builtins.input", read_line)
    with pytest.raises(SystemExit, match="No text provided"):
        read_text()
