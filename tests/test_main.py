import pytest

from voicer.cli import main


def test_main_exits_when_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert str(exc_info.value) == "Set OPENAI_API_KEY before running this script."
