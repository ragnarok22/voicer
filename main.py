import argparse
import os
import re
import stat
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Literal, TextIO

import httpx2
import openai
import tiktoken
from openai import OpenAI

VOICES = (
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
LEGACY_VOICES = frozenset(
    ("alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer")
)
DEFAULT_MODEL = "gpt-4o-mini-tts"
OUTPUT_DIR = Path("outputs")
DEFAULT_VOICE = "marin"
type ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
DEFAULT_RESPONSE_FORMAT: ResponseFormat = "mp3"
RESPONSE_FORMATS = ("mp3", "opus", "aac", "flac", "wav", "pcm")
MAX_INPUT_CHARACTERS = 4096
MINI_MAX_INPUT_TOKENS = 2000


class CliError(ValueError):
    pass


def read_text() -> str:
    print("Paste the text to turn into audio. Submit an empty line when finished.")
    lines: list[str] = []

    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)

    text = "\n".join(lines).strip()
    if not text:
        raise SystemExit("No text provided.")

    return text


def parse_voice_selection(
    raw_selection: str,
    *,
    default: str | None = DEFAULT_VOICE,
) -> list[str]:
    raw_selection = raw_selection.strip()
    if not raw_selection:
        if default is None:
            raise CliError("No voices selected.")
        return [default]
    if raw_selection.lower() == "all":
        return list(VOICES)

    selected: list[str] = []
    for item in raw_selection.split(","):
        value = item.strip().lower()
        if not value:
            continue

        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(VOICES):
                selected.append(VOICES[index - 1])
                continue
        elif value in VOICES:
            selected.append(value)
            continue

        raise CliError(f"Unknown voice selection: {item.strip()}")

    selected = list(dict.fromkeys(selected))
    if not selected:
        raise CliError("No voices selected.")

    return selected


def select_voices() -> list[str]:
    print("Available voices:")
    for index, voice in enumerate(VOICES, start=1):
        print(f"  {index}. {voice}")

    raw_selection = input(
        f"Select voices by number/name, comma-separated, or 'all' [{DEFAULT_VOICE}]: "
    )
    try:
        return parse_voice_selection(raw_selection)
    except CliError as error:
        raise SystemExit(str(error)) from error


def read_stdin(stdin: TextIO | None = None) -> str:
    stream = stdin if stdin is not None else sys.stdin
    if stream is None:
        raise SystemExit("stdin is unavailable.")

    text = stream.read().strip()
    if not text:
        raise SystemExit("No text provided on stdin.")

    return text


def read_input_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        raise SystemExit(f"Input file is not valid UTF-8: {path}") from None
    except OSError as error:
        raise SystemExit(
            f"Could not read input file {path}: {error.strerror}"
        ) from error

    if not text:
        raise SystemExit(f"Input file is empty: {path}")

    return text


def resolve_text(*, text: str | None, input_file: Path | None, use_stdin: bool) -> str:
    sources = sum(source is not None for source in (text, input_file)) + int(use_stdin)
    if sources > 1:
        raise SystemExit(
            "Provide text using only one source: argument, --file, or --stdin."
        )

    if text is not None:
        text = text.strip()
        if not text:
            raise SystemExit("No text provided.")
        return text
    if input_file is not None:
        return read_input_file(input_file)
    if use_stdin:
        return read_stdin()
    if not sys.stdin.isatty():
        return read_stdin()

    return read_text()


def filename_base(text: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())[:8]
    return "-".join(words) or "voice"


def count_input_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")

    return len(encoding.encode_ordinary(text))


def _uses_character_billing(model: str) -> bool:
    return (
        re.fullmatch(r"tts-1(?:-hd)?(?:-[0-9]{4}(?:-[0-9]{2}-[0-9]{2})?)?", model)
        is not None
    )


def usd_per_1m_input_tokens(model: str) -> float | None:
    if _uses_character_billing(model):
        return None

    raw_price = os.environ.get("OPENAI_TTS_USD_PER_1M_TOKENS")
    if raw_price is None:
        return None

    try:
        price = float(raw_price)
    except ValueError:
        raise SystemExit("OPENAI_TTS_USD_PER_1M_TOKENS must be a number.") from None

    if not isfinite(price) or price < 0:
        raise SystemExit(
            "OPENAI_TTS_USD_PER_1M_TOKENS must be finite and non-negative."
        )
    return price


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def format_openai_error(
    error: openai.OpenAIError | httpx2.RequestError,
    *,
    request_id: str | None = None,
) -> str:
    body = getattr(error, "body", None)
    error_body = body if isinstance(body, dict) else {}
    if isinstance(error_body.get("error"), dict):
        error_body = error_body["error"]
    status = getattr(error, "status_code", None)
    quota = any(
        value == "insufficient_quota"
        for value in (
            error_body.get("code"),
            error_body.get("type"),
            getattr(error, "code", None),
            getattr(error, "type", None),
        )
    )

    if status == 429 and quota:
        message = (
            "OpenAI quota exceeded. Check your plan and billing details. "
            "OpenAI error code/type: insufficient_quota."
        )
    elif isinstance(error, (openai.APITimeoutError, httpx2.TimeoutException)):
        message = "OpenAI request or audio download timed out. Try again."
    elif isinstance(error, (openai.APIConnectionError, httpx2.RequestError)):
        message = (
            "OpenAI connection or audio stream failed. "
            "Check your network connection and try again."
        )
    elif status == 401:
        message = "OpenAI authentication failed. Check OPENAI_API_KEY."
    elif status == 403:
        message = "OpenAI permission denied. Check project and model access."
    elif status == 429:
        message = "OpenAI rate limit exceeded. Wait before trying again."
    elif status in (400, 422):
        kind = "bad request" if status == 400 else "invalid request"
        message = (
            f"OpenAI {kind}. Check the text length, model, voice, audio format, "
            "instructions and speed."
        )
    elif isinstance(status, int) and status >= 500:
        message = f"OpenAI server error (HTTP {status}). Try again later."
    elif isinstance(status, int):
        message = f"OpenAI request failed (HTTP {status}). Check request settings."
    else:
        message = "OpenAI request failed. Check request settings and try again."

    # SDK messages/bodies can echo credentials or input; report only safe metadata.
    request_id = getattr(error, "request_id", None) or request_id
    if isinstance(request_id, str) and re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", request_id
    ):
        message += f" Request ID: {request_id}."
    return message


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


def format_cost(
    total_input_tokens: int,
    token_price: float | None,
    *,
    model: str = DEFAULT_MODEL,
) -> list[str]:
    disclaimer = "Excludes generated audio cost; this estimate is not a bill."
    if _uses_character_billing(model):
        return [
            "Estimated text input cost: unavailable",
            f"{model} uses character-based billing; no token price applies.",
            disclaimer,
        ]
    if token_price is None:
        return [
            "Estimated text input cost: unavailable",
            "Set OPENAI_TTS_USD_PER_1M_TOKENS to estimate text input cost.",
            disclaimer,
        ]

    if not isfinite(token_price) or token_price < 0:
        raise SystemExit(
            "OPENAI_TTS_USD_PER_1M_TOKENS must be finite and non-negative."
        )
    estimated_cost = total_input_tokens / 1_000_000 * token_price
    return [
        f"Estimated text input cost: ${estimated_cost:.6f} USD",
        f"Price used: ${token_price:g} USD per 1M text input tokens",
        disclaimer,
    ]


def print_estimate(
    *,
    text: str,
    voices: list[str],
    model: str,
    instructions: str | None = None,
) -> None:
    input_tokens = count_input_tokens(text, model)
    if instructions:
        input_tokens += count_input_tokens(instructions, model)
    total_input_tokens = input_tokens * len(voices)
    token_price = usd_per_1m_input_tokens(model)

    print("Estimate")
    print(f"Model: {model}")
    print(f"Voices: {', '.join(voices)}")
    print(
        "Estimated input tokens: "
        f"{total_input_tokens:,} ({input_tokens:,} per file x {len(voices)})"
    )
    if instructions:
        print(
            "Includes instruction tokens per file as a conservative estimate, "
            "not exact billed usage."
        )
    for line in format_cost(total_input_tokens, token_price, model=model):
        print(line)


def print_summary(
    *,
    generated_files: list[Path],
    input_tokens: int,
    voices: list[str],
    token_price: float | None,
    total_elapsed: float,
    model: str = DEFAULT_MODEL,
) -> None:
    total_input_tokens = input_tokens * len(voices)

    print("\nSummary")
    print(f"Files generated: {len(generated_files)}")
    print(
        "Estimated input tokens: "
        f"{total_input_tokens:,} ({input_tokens:,} per file x {len(voices)})"
    )
    for line in format_cost(total_input_tokens, token_price, model=model):
        print(line)
    print(f"Total time: {format_seconds(total_elapsed)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voicer",
        description="Generate OpenAI text-to-speech audio files.",
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to synthesize. If omitted, voicer reads piped stdin or opens an interactive prompt.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        dest="input_file",
        help="Read text from a UTF-8 file.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read text from stdin explicitly.",
    )
    parser.add_argument(
        "-v",
        "--voice",
        action="append",
        dest="voice_selections",
        help=(
            "Voice name, number, comma-list, or 'all'. Repeat the flag for multiple voices. "
            f"Default: {DEFAULT_VOICE} (alloy for tts-1/tts-1-hd)."
        ),
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Print voices available for the selected model and exit.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=os.environ.get("OPENAI_TTS_MODEL", DEFAULT_MODEL),
        help="OpenAI TTS model. Default: %(default)s.",
    )
    parser.add_argument(
        "--instructions",
        help="Voice style instructions. Not supported by tts-1 or tts-1-hd.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed from 0.25 to 4.0. Default: %(default)s.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Request timeout in seconds (positive). Default: %(default)s.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="SDK retries before streaming starts (non-negative). Default: %(default)s.",
    )
    parser.add_argument(
        "--format",
        choices=RESPONSE_FORMATS,
        default=DEFAULT_RESPONSE_FORMAT,
        dest="response_format",
        help=f"Audio response format. Default: {DEFAULT_RESPONSE_FORMAT}.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        dest="output_file",
        help="Exact output file path. Only valid with one voice.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory for generated files. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --output if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print token and cost estimates without calling OpenAI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="voicer 0.1.0",
    )
    return parser


def available_voices(model: str) -> tuple[str, ...]:
    if _uses_character_billing(model):
        return tuple(voice for voice in VOICES if voice in LEGACY_VOICES)
    return VOICES


def resolve_voices(
    selections: list[str] | None, model: str = DEFAULT_MODEL
) -> list[str]:
    if not selections:
        return ["alloy" if _uses_character_billing(model) else DEFAULT_VOICE]

    voices: list[str] = []
    for selection in selections:
        if selection.strip().lower() == "all":
            voices.extend(available_voices(model))
        else:
            voices.extend(parse_voice_selection(selection, default=None))

    voices = list(dict.fromkeys(voices))
    unsupported = [voice for voice in voices if voice not in available_voices(model)]
    if unsupported:
        raise CliError(f"Voices not supported by {model}: {', '.join(unsupported)}.")
    return voices


def validate_options(args: argparse.Namespace) -> None:
    args.model = args.model.strip()
    if not args.model:
        raise SystemExit("--model must not be empty.")
    if not isfinite(args.speed) or not 0.25 <= args.speed <= 4.0:
        raise SystemExit("--speed must be finite and between 0.25 and 4.0.")
    if not isfinite(args.timeout) or args.timeout <= 0:
        raise SystemExit("--timeout must be finite and positive.")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be non-negative.")
    if args.instructions is not None:
        args.instructions = args.instructions.strip()
        if not args.instructions:
            raise SystemExit("--instructions must not be empty.")
        if _uses_character_billing(args.model):
            raise SystemExit(f"--instructions is not supported by {args.model}.")


def validate_text(text: str, model: str, instructions: str | None = None) -> int:
    if len(text) > MAX_INPUT_CHARACTERS:
        raise SystemExit(
            f"Speech input exceeds {MAX_INPUT_CHARACTERS} characters. "
            "Provide a shorter text."
        )
    input_tokens = count_input_tokens(text, model)
    if instructions:
        input_tokens += count_input_tokens(instructions, model)
    if (model == DEFAULT_MODEL or model.startswith(f"{DEFAULT_MODEL}-")) and (
        input_tokens > MINI_MAX_INPUT_TOKENS
    ):
        raise SystemExit(
            f"Input exceeds the estimated {MINI_MAX_INPUT_TOKENS} input tokens for {model} "
            "(including instructions). Provide shorter text or instructions."
        )
    return input_tokens


def run(args: argparse.Namespace) -> None:
    validate_options(args)
    if args.list_voices:
        for index, voice in enumerate(VOICES, start=1):
            if voice in available_voices(args.model):
                print(f"{index:>2}. {voice}")
        return

    try:
        voices = resolve_voices(args.voice_selections, args.model)
    except CliError as error:
        raise SystemExit(str(error)) from error

    if args.output_file is not None and len(voices) != 1:
        raise SystemExit("--output can only be used with one voice.")

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running this script.")

    text = resolve_text(
        text=args.text, input_file=args.input_file, use_stdin=args.stdin
    )
    input_tokens = validate_text(text, args.model, args.instructions)

    if args.dry_run:
        print_estimate(
            text=text, voices=voices, model=args.model, instructions=args.instructions
        )
        return

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    token_price = usd_per_1m_input_tokens(args.model)

    total_start = perf_counter()
    with OpenAI(timeout=args.timeout, max_retries=args.max_retries) as client:
        generated_files = generate_audio_files(
            client=client,
            voices=voices,
            text=text,
            model=args.model,
            output_dir=args.output_dir,
            response_format=args.response_format,
            output_file=args.output_file,
            overwrite=args.force,
            timestamp=timestamp,
            instructions=args.instructions,
            speed=args.speed,
        )

    total_elapsed = perf_counter() - total_start
    print_summary(
        generated_files=generated_files,
        input_tokens=input_tokens,
        voices=voices,
        token_price=token_price,
        total_elapsed=total_elapsed,
        model=args.model,
    )


def main(argv: Sequence[str] = ()) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)


def cli() -> None:
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        raise SystemExit("Generation cancelled.") from None


if __name__ == "__main__":
    cli()
