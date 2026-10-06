from unittest.mock import MagicMock

import httpx2 as httpx
import openai
import pytest

from main import format_openai_error, generate_audio_files


def rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/speech")
    response = httpx.Response(
        429,
        request=request,
        json={
            "error": {
                "message": "You exceeded your current quota, please check your plan and billing details.",
                "type": "insufficient_quota",
                "param": None,
                "code": "insufficient_quota",
            }
        },
    )
    return openai.RateLimitError(
        "Error code: 429 - insufficient quota",
        response=response,
        body=response.json(),
    )


def test_format_openai_error_explains_insufficient_quota() -> None:
    message = format_openai_error(rate_limit_error())

    assert "OpenAI quota exceeded" in message
    assert "plan and billing" in message
    assert "insufficient_quota" in message


def test_generate_audio_files_exits_cleanly_on_rate_limit(tmp_path) -> None:
    class Speech:
        def create(self, **kwargs):
            raise rate_limit_error()

    class Client:
        audio = type(
            "Audio",
            (),
            {
                "speech": type(
                    "SpeechResponses", (), {"with_streaming_response": Speech()}
                )()
            },
        )()

    with pytest.raises(SystemExit) as exc_info:
        generate_audio_files(
            client=MagicMock(spec=openai.OpenAI, wraps=Client()),
            voices=["alloy"],
            text="Hello world",
            model="gpt-4o-mini-tts",
            output_dir=tmp_path,
        )

    assert "OpenAI quota exceeded" in str(exc_info.value)


def test_generate_audio_files_prints_progress_before_request(tmp_path, capsys) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def stream_to_file(self, output_path):
            output_path.write_bytes(b"audio")

    class Speech:
        def create(self, **kwargs):
            return Response()

    class Client:
        audio = type(
            "Audio",
            (),
            {
                "speech": type(
                    "SpeechResponses", (), {"with_streaming_response": Speech()}
                )()
            },
        )()

    generate_audio_files(
        client=MagicMock(spec=openai.OpenAI, wraps=Client()),
        voices=["alloy"],
        text="Hello world",
        model="gpt-4o-mini-tts",
        output_dir=tmp_path,
        timestamp="20260101-120000",
    )

    output = capsys.readouterr().out
    assert "Generating alloy" in output
    assert "Generated" in output
