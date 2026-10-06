from collections.abc import Iterator
from pathlib import Path

import httpx2
import openai
import pytest

import main


class BrokenAudio(httpx2.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"partial audio"
        raise httpx2.ReadError("stream interrupted")


@pytest.mark.parametrize("existing", [False, True])
def test_failed_download_preserves_destination(tmp_path: Path, existing: bool) -> None:
    output = tmp_path / "voice.mp3"
    if existing:
        output.write_bytes(b"original audio")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, stream=BrokenAudio(), request=request)

    with (
        openai.OpenAI(
            api_key="test-key",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            max_retries=0,
        ) as client,
        pytest.raises(SystemExit, match="(?i)(stream|connection|download)"),
    ):
        main.generate_audio_files(
            client=client,
            voices=["marin"],
            text="Hello",
            model=main.DEFAULT_MODEL,
            output_dir=tmp_path,
            output_file=output,
            overwrite=existing,
        )

    if existing:
        assert output.read_bytes() == b"original audio"
        assert list(tmp_path.iterdir()) == [output]
    else:
        assert list(tmp_path.iterdir()) == []


def test_sdk_quota_error_is_recognized(tmp_path: Path) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            429,
            request=request,
            json={"error": {"code": "insufficient_quota", "message": "Quota exceeded"}},
        )

    with (
        openai.OpenAI(
            api_key="test-key",
            http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            max_retries=0,
        ) as client,
        pytest.raises(SystemExit, match="OpenAI quota exceeded"),
    ):
        main.generate_audio_files(
            client=client,
            voices=["marin"],
            text="Hello",
            model=main.DEFAULT_MODEL,
            output_dir=tmp_path,
        )


@pytest.mark.parametrize("price", ["-1", "nan", "inf", "-inf"])
def test_price_must_be_finite_and_nonnegative(monkeypatch, price: str) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    with pytest.raises(SystemExit, match="finite.*non-negative"):
        main.usd_per_1m_input_tokens(main.DEFAULT_MODEL)


def test_legacy_model_does_not_use_token_price(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", "0.6")
    assert main.usd_per_1m_input_tokens("tts-1") is None
