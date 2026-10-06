import builtins
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import openai
import pytest

import main


def client_for(handler: Callable[[httpx2.Request], httpx2.Response]) -> openai.OpenAI:
    return openai.OpenAI(
        api_key="test-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )


def generate(
    client: openai.OpenAI,
    tmp_path: Path,
    *,
    voices: list[str] | None = None,
    response_format: main.ResponseFormat = "mp3",
    output_file: Path | None = None,
    overwrite: bool = False,
    instructions: str | None = None,
    speed: float = 1.0,
) -> list[Path]:
    return main.generate_audio_files(
        client=client,
        voices=voices if voices is not None else ["marin"],
        text="Hello",
        model=main.DEFAULT_MODEL,
        output_dir=tmp_path,
        timestamp="fixed",
        response_format=response_format,
        output_file=output_file,
        overwrite=overwrite,
        instructions=instructions,
        speed=speed,
    )


@pytest.mark.parametrize("response_format", main.RESPONSE_FORMATS)
@pytest.mark.parametrize("instructions", [None, "Speak softly"])
def test_speech_http_contract(tmp_path, response_format, instructions) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio bytes")

    with client_for(handler) as client:
        files = generate(
            client,
            tmp_path,
            response_format=response_format,
            instructions=instructions,
            speed=1.25,
        )

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/audio/speech"
    assert request.headers["accept"] == "application/octet-stream"
    expected = {
        "model": main.DEFAULT_MODEL,
        "voice": "marin",
        "input": "Hello",
        "response_format": response_format,
        "speed": 1.25,
        "stream_format": "audio",
    }
    if instructions is not None:
        expected["instructions"] = instructions
    assert json.loads(request.content) == expected
    assert files == [tmp_path / f"hello-marin-fixed.{response_format}"]
    assert files[0].read_bytes() == b"audio bytes"
    assert list(tmp_path.iterdir()) == files


@pytest.mark.parametrize("overwrite", [False, True])
def test_publish_only_after_stream_and_close(tmp_path, overwrite) -> None:
    output = tmp_path / "voice.mp3"
    if overwrite:
        output.write_bytes(b"original")
    closed = False

    def assert_original():
        if overwrite:
            assert output.read_bytes() == b"original"
        else:
            assert not output.exists()

    class Audio(httpx2.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            assert_original()
            yield b"first"
            assert_original()
            yield b"second"

        def close(self):
            nonlocal closed
            assert_original()
            closed = True

    with client_for(lambda request: httpx2.Response(200, stream=Audio())) as client:
        assert generate(client, tmp_path, output_file=output, overwrite=overwrite) == [
            output
        ]

    assert closed
    assert output.read_bytes() == b"firstsecond"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt, httpx2.ReadTimeout, httpx2.ReadError]
)
@pytest.mark.parametrize("during_close", [False, True])
def test_failed_download_cleans_up_on_interrupt_or_close(
    tmp_path, failure, during_close
) -> None:
    output = tmp_path / "voice.mp3"
    output.write_bytes(b"original")

    class Audio(httpx2.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            yield b"partial"
            if not during_close:
                raise failure("failed download")

        def close(self):
            if during_close:
                raise failure("failed close")

    client = client_for(
        lambda request: httpx2.Response(
            200,
            stream=Audio(),
            headers={"x-request-id": "req_stream"},
        )
    )
    try:
        expected = KeyboardInterrupt if failure is KeyboardInterrupt else SystemExit
        with pytest.raises(expected) as caught:
            generate(client, tmp_path, output_file=output, overwrite=True)
        if expected is SystemExit:
            assert "req_stream" in str(caught.value)
        assert output.read_bytes() == b"original"
        assert list(tmp_path.iterdir()) == [output]
    finally:
        client.close()


def test_no_force_preserves_file_created_during_request(tmp_path) -> None:
    output = tmp_path / "voice.mp3"

    def handler(request):
        output.write_bytes(b"concurrent writer")
        return httpx2.Response(200, content=b"new audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="already exists.*--force"),
    ):
        generate(client, tmp_path, output_file=output)
    assert output.read_bytes() == b"concurrent writer"
    assert list(tmp_path.iterdir()) == [output]


def test_preflight_checks_every_destination_before_requests(tmp_path) -> None:
    output = tmp_path / "hello-cedar-fixed.mp3"
    output.write_bytes(b"existing")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="already exists"),
    ):
        generate(client, tmp_path, voices=["marin", "cedar"])
    assert requests == []
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [False, True])
def test_filesystem_preflight_rejects_directory_destination(
    tmp_path, overwrite
) -> None:
    output = tmp_path / "voice.mp3"
    output.mkdir()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="(?i)(output|file|directory)"),
    ):
        generate(client, tmp_path, output_file=output, overwrite=overwrite)
    assert requests == []
    assert list(tmp_path.iterdir()) == [output]


def test_no_force_rejects_dangling_symlink_before_request(tmp_path) -> None:
    output = tmp_path / "voice.mp3"
    output.symlink_to(tmp_path / "absent")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="already exists"),
    ):
        generate(client, tmp_path, output_file=output)
    assert requests == []
    assert output.is_symlink()
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("operation", ["mkdir", "temporary", "publish"])
def test_filesystem_failures_are_clear_and_cleanup(
    tmp_path, monkeypatch, operation
) -> None:
    output = tmp_path / "voice.mp3"
    requests = []

    def fail(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    if operation == "mkdir":
        monkeypatch.setattr(Path, "mkdir", fail)
    elif operation == "temporary":
        monkeypatch.setattr(main.tempfile, "NamedTemporaryFile", fail)
    else:
        monkeypatch.setattr(main.os, "replace", fail)

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="(?i)output.*Permission denied"),
    ):
        generate(client, tmp_path, output_file=output, overwrite=True)
    assert len(requests) == (1 if operation == "publish" else 0)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (401, {"error": {"message": "secret-key"}}, "authentication"),
        (403, {"error": None}, "permission"),
        (429, {"error": {"code": "rate_limit_exceeded"}}, "rate limit"),
        (429, {"error": {"type": "insufficient_quota"}}, "quota exceeded"),
        (429, {"code": "insufficient_quota"}, "quota exceeded"),
        (400, {"error": []}, "bad request"),
        (422, [], "invalid request"),
        (500, {"error": "secret-key"}, "server error"),
        (503, "secret-key", "server error"),
    ],
)
def test_sdk_errors_are_actionable_without_secrets(
    tmp_path, status, body, message
) -> None:
    def handler(request):
        return httpx2.Response(
            status,
            json=body,
            headers={"x-request-id": "req_test"},
        )

    with client_for(handler) as client, pytest.raises(SystemExit) as caught:
        generate(client, tmp_path)
    rendered = str(caught.value)
    assert message in rendered.lower()
    assert "req_test" in rendered
    assert "secret-key" not in rendered
    assert "test-key" not in rendered
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", [httpx2.ConnectError, httpx2.ConnectTimeout])
def test_sdk_connection_errors_are_clean(tmp_path, failure) -> None:
    def handler(request):
        raise failure("secret-key", request=request)

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="(?i)(connection|timed out)") as caught,
    ):
        generate(client, tmp_path)
    assert "secret-key" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


def test_preflight_cleans_all_temporaries_when_later_reservation_fails(
    tmp_path,
    monkeypatch,
) -> None:
    reserve = main.tempfile.NamedTemporaryFile
    reservations = 0
    requests = []

    def reserve_or_fail(*args, **kwargs):
        nonlocal reservations
        reservations += 1
        if reservations == 2:
            raise OSError(28, "No space left on device")
        return reserve(*args, **kwargs)

    monkeypatch.setattr(main.tempfile, "NamedTemporaryFile", reserve_or_fail)

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, content=b"audio")

    with (
        client_for(handler) as client,
        pytest.raises(SystemExit, match="output.*No space left"),
    ):
        generate(client, tmp_path, voices=["marin", "cedar"])
    assert reservations == 2
    assert requests == []
    assert list(tmp_path.iterdir()) == []


def test_failed_download_cleans_up_on_file_write_failure(tmp_path, monkeypatch) -> None:
    output = tmp_path / "voice.mp3"
    output.write_bytes(b"original")
    file_open = builtins.open

    def open_or_fail(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).suffix == ".tmp":
            raise OSError(28, "No space left on device")
        return file_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", open_or_fail)
    with (
        client_for(lambda request: httpx2.Response(200, content=b"audio")) as client,
        pytest.raises(SystemExit, match="output.*No space left"),
    ):
        generate(client, tmp_path, output_file=output, overwrite=True)
    assert output.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [output]
