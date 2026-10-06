import json
from io import StringIO
from pathlib import Path

import httpx2
import openai
import pytest

import main


@pytest.fixture(autouse=True)
def offline_tokenizer(monkeypatch):
    monkeypatch.setattr(
        main, "count_input_tokens", lambda text, model: len(text.split())
    )
    monkeypatch.delenv("OPENAI_TTS_USD_PER_1M_TOKENS", raising=False)


def test_current_catalog_preserves_voice_numbers() -> None:
    assert main.VOICES == (
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "sage",
        "shimmer",
        "verse",
        "marin",
        "cedar",
        "fable",
        "nova",
        "onyx",
    )
    assert main.resolve_voices(["9,11,12,13"]) == ["marin", "fable", "nova", "onyx"]


@pytest.mark.parametrize("model", ["tts-1", "tts-1-hd", "tts-1-1106"])
def test_legacy_voice_list_preserves_global_numbers(model, capsys) -> None:
    main.main(["--list-voices", "--model", model])
    output = capsys.readouterr().out
    assert "11. fable" in output
    assert "12. nova" in output
    assert "13. onyx" in output
    assert "marin" not in output
    assert "ballad" not in output


def test_legacy_default_and_all_are_compatible(capsys) -> None:
    main.main(["--dry-run", "--model", "tts-1", "Hello"])
    assert "Voices: alloy" in capsys.readouterr().out
    main.main(["--dry-run", "--model", "tts-1", "--voice", "all", "Hello"])
    output = capsys.readouterr().out
    assert "marin" not in output
    assert "fable" in output


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--model", "tts-1", "--voice", "marin"], "not supported"),
        (["--model", "tts-1-hd", "--instructions", "Whisper"], "instructions"),
        (["--instructions", "   "], "instructions"),
        (["--speed", "0.24"], "speed"),
        (["--speed", "4.01"], "speed"),
        (["--speed", "nan"], "speed"),
        (["--speed", "inf"], "speed"),
        (["--timeout", "0"], "timeout"),
        (["--timeout", "nan"], "timeout"),
        (["--max-retries", "-1"], "max-retries"),
        (["--model", " "], "model"),
    ],
)
def test_invalid_requests_fail_before_client_creation(monkeypatch, arguments, message):
    def unexpected_client(*args, **kwargs):
        pytest.fail("Invalid request must not create a client")

    monkeypatch.setattr(main, "OpenAI", unexpected_client)
    with pytest.raises(SystemExit, match=message):
        main.main(["--dry-run", *arguments, "Hello"])


def test_character_limit_rejected_without_network() -> None:
    with pytest.raises(SystemExit, match="4096 characters"):
        main.main(["--dry-run", "x" * 4097])


def test_mini_token_limit_includes_instructions(monkeypatch) -> None:
    monkeypatch.setattr(main, "count_input_tokens", lambda text, model: len(text))
    with pytest.raises(SystemExit, match="2000.*tokens"):
        main.main(["--dry-run", "--instructions", "y" * 1001, "x" * 1000])


def test_limit_boundary_and_unknown_model(capsys) -> None:
    main.main(["--dry-run", "--speed", "0.25", "x" * 4096])
    assert "Estimate" in capsys.readouterr().out
    main.main(["--dry-run", "--model", "future-tts-model", "--speed", "4", "Hello"])
    assert "future-tts-model" in capsys.readouterr().out


def test_cli_passes_controls_and_closes_client(monkeypatch, tmp_path: Path, capsys):
    requests = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, content=b"audio")

    client = openai.OpenAI(
        api_key="test-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )

    def create_client(**kwargs):
        assert kwargs == {"timeout": 45.0, "max_retries": 0}
        return client

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", "0.6")
    monkeypatch.setattr(main, "OpenAI", create_client)
    output = tmp_path / "voice.wav"
    main.main(
        [
            "--voice",
            "cedar",
            "--instructions",
            "Speak softly",
            "--speed",
            "1.25",
            "--timeout",
            "45",
            "--max-retries",
            "0",
            "--format",
            "wav",
            "--output",
            str(output),
            "Hello world",
        ]
    )
    assert client.is_closed()
    assert output.read_bytes() == b"audio"
    assert requests[0]["instructions"] == "Speak softly"
    assert requests[0]["speed"] == 1.25
    assert requests[0]["voice"] == "cedar"
    summary = capsys.readouterr().out
    assert "4 (4 per file x 1)" in summary
    assert "Excludes generated audio cost" in summary


def test_dry_run_and_listing_do_not_create_client(monkeypatch, capsys):
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: pytest.fail("Network client"))
    main.main(["--dry-run", "--instructions", "Speak softly", "Hello world"])
    assert "4 (4 per file x 1)" in capsys.readouterr().out
    main.main(["--list-voices"])
    assert "onyx" in capsys.readouterr().out


def test_invalid_utf8_file_is_a_cli_error(tmp_path: Path) -> None:
    input_file = tmp_path / "input.txt"
    input_file.write_bytes(b"\xff")
    with pytest.raises(SystemExit, match="UTF-8"):
        main.main(["--dry-run", "--file", str(input_file)])


@pytest.mark.parametrize("source", ["file", "stdin", "pipe", "interactive"])
def test_cli_input_sources(monkeypatch, tmp_path, capsys, source):
    arguments = ["--dry-run"]
    if source == "file":
        path = tmp_path / "input.txt"
        path.write_text("  Hola mundo\n", encoding="utf-8")
        arguments.extend(["--file", str(path)])
    elif source in ("stdin", "pipe"):
        monkeypatch.setattr(main.sys, "stdin", StringIO("  Hola mundo\n"))
        if source == "stdin":
            arguments.append("--stdin")
    else:
        stream = StringIO()
        monkeypatch.setattr(stream, "isatty", lambda: True)
        monkeypatch.setattr(main.sys, "stdin", stream)
        lines = iter(["Hola mundo", ""])
        monkeypatch.setattr("builtins.input", lambda: next(lines))
    main.main(arguments)
    assert "2 (2 per file x 1)" in capsys.readouterr().out


@pytest.mark.parametrize("exists", [False, True])
def test_invalid_file_input_is_actionable(tmp_path, exists):
    path = tmp_path / "input.txt"
    if exists:
        path.write_text("  ", encoding="utf-8")
    with pytest.raises(SystemExit, match="empty|Could not read"):
        main.main(["--dry-run", "--file", str(path)])


def test_cli_failure_closes_client(monkeypatch, tmp_path):
    client = openai.OpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(
            transport=httpx2.MockTransport(
                lambda request: httpx2.Response(
                    401, json={"error": {"message": "Unauthorized"}}
                )
            )
        ),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "OpenAI", lambda **kwargs: client)
    with pytest.raises(SystemExit, match="authentication"):
        main.main(["--output", str(tmp_path / "voice.mp3"), "Hola"])
    assert client.is_closed()
    assert list(tmp_path.iterdir()) == []


def test_cli_cancellation_is_clean(monkeypatch):
    def interrupted(argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "main", interrupted)
    with pytest.raises(SystemExit, match="cancelled"):
        main.cli()
