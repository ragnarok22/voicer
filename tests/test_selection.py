import pytest

from main import VOICES, select_voices


@pytest.mark.parametrize(
    ("raw_selection", "expected"),
    [
        ("", ["marin"]),
        ("all", list(VOICES)),
        ("1, echo, 1, ALLOY", ["alloy", "echo"]),
        (" 2 , shimmer ", ["ash", "shimmer"]),
    ],
)
def test_select_voices_accepts_supported_selection_forms(
    monkeypatch,
    raw_selection: str,
    expected: list[str],
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: raw_selection)

    assert select_voices() == expected


@pytest.mark.parametrize("raw_selection", ["unknown", "999", "alloy, unknown"])
def test_select_voices_rejects_unknown_values(monkeypatch, raw_selection: str) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: raw_selection)

    with pytest.raises(SystemExit) as exc_info:
        select_voices()

    assert "Unknown voice selection" in str(exc_info.value)


def test_select_voices_rejects_empty_comma_selection(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: ",,,")

    with pytest.raises(SystemExit) as exc_info:
        select_voices()

    assert str(exc_info.value) == "No voices selected."
