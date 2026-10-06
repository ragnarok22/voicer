from io import StringIO
from unittest.mock import MagicMock

import pytest

import main


def test_main_lists_voices_without_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    main.main(["--list-voices"])

    output = capsys.readouterr().out
    assert "alloy" in output
    assert "cedar" in output


def test_main_dry_run_does_not_require_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main, "count_input_tokens", lambda text, model: 2)

    main.main(["--dry-run", "--voice", "alloy,echo", "Hello world"])

    output = capsys.readouterr().out
    assert "Estimate" in output
    assert "Voices: alloy, echo" in output
    assert "Estimated input tokens" in output


def test_resolve_text_rejects_multiple_sources(tmp_path) -> None:
    input_file = tmp_path / "input.txt"
    input_file.write_text("from file", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main.resolve_text(text="from arg", input_file=input_file, use_stdin=False)

    assert "only one source" in str(exc_info.value)


def test_read_stdin_strips_text() -> None:
    assert main.read_stdin(StringIO("  hello\n")) == "hello"


def test_generate_audio_files_refuses_existing_output_without_force(tmp_path) -> None:
    output_file = tmp_path / "voice.mp3"
    output_file.write_bytes(b"existing")

    with pytest.raises(SystemExit) as exc_info:
        main.generate_audio_files(
            client=MagicMock(spec=main.OpenAI),
            voices=["alloy"],
            text="Hello world",
            model="gpt-4o-mini-tts",
            output_dir=tmp_path,
            output_file=output_file,
        )

    assert "already exists" in str(exc_info.value)
