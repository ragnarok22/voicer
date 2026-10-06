"""Stream speech audio and safely publish files after downloads complete."""

import os
import re
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from time import perf_counter

import httpx2
import openai
from openai import OpenAI

from .config import DEFAULT_RESPONSE_FORMAT, ResponseFormat
from .errors import format_openai_error
from .reporting import format_seconds


def filename_base(text: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())[:8]
    return "-".join(words) or "voice"


def _output_exists_error(output_path: Path) -> SystemExit:
    return SystemExit(
        f"Output file already exists: {output_path}. Use --force to replace it."
    )


def _cleanup_audio_temporaries(temporary_paths: list[Path]) -> None:
    failure: tuple[Path, OSError] | None = None
    for path in temporary_paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            failure = (path, error)
    if failure is not None:
        path, error = failure
        raise SystemExit(
            f"Could not remove temporary output file {path}: {error.strerror or error}"
        ) from error


def generate_audio_files(
    *,
    client: OpenAI,
    voices: list[str],
    text: str,
    model: str,
    output_dir: Path,
    response_format: ResponseFormat = DEFAULT_RESPONSE_FORMAT,
    output_file: Path | None = None,
    overwrite: bool = False,
    timestamp: str | None = None,
    instructions: str | None = None,
    speed: float = 1.0,
) -> list[Path]:
    timestamp = timestamp or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    generated_files: list[Path] = []

    if output_file is not None and len(voices) != 1:
        raise SystemExit("--output can only be used with one voice.")

    output_paths = [
        output_file
        or output_dir / (f"{filename_base(text)}-{voice}-{timestamp}.{response_format}")
        for voice in voices
    ]
    if len(set(output_paths)) != len(output_paths):
        raise SystemExit("Multiple voices resolve to the same output file.")
    temporary_paths: list[Path] = []
    output_path = output_file or output_dir
    request_id: str | None = None
    try:
        # Check every destination and reserve writable same-directory staging files
        # before making the first billable request.
        for output_path in output_paths:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                mode = output_path.lstat().st_mode
            except FileNotFoundError:
                pass
            else:
                if not overwrite:
                    raise _output_exists_error(output_path)
                if not stat.S_ISREG(mode):
                    raise SystemExit(
                        f"Output path is not a regular file: {output_path}"
                    )
            with tempfile.NamedTemporaryFile(
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_paths.append(Path(temporary.name))

        for voice, output_path, temporary_path in zip(
            voices,
            output_paths,
            temporary_paths,
            strict=True,
        ):
            request_id = None
            file_start = perf_counter()
            print(f"Generating {voice} -> {output_path}...", flush=True)
            with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
                instructions=instructions if instructions is not None else openai.omit,
                speed=speed,
                stream_format="audio",
            ) as response:
                request_id = getattr(response, "headers", {}).get("x-request-id")
                response.stream_to_file(temporary_path)
            # Both the file writer and HTTP response must close successfully first.
            if overwrite:
                os.replace(temporary_path, output_path)
            else:
                try:
                    os.link(temporary_path, output_path)
                except FileExistsError:
                    raise _output_exists_error(output_path) from None
                temporary_path.unlink()
            generated_files.append(output_path)
            print(
                f"Generated {output_path} in {format_seconds(perf_counter() - file_start)}"
            )
    except (openai.OpenAIError, httpx2.RequestError) as error:
        raise SystemExit(format_openai_error(error, request_id=request_id)) from error
    except OSError as error:
        raise SystemExit(
            f"Could not write output file {output_path}: {error.strerror or error}"
        ) from error
    finally:
        _cleanup_audio_temporaries(temporary_paths)

    return generated_files
