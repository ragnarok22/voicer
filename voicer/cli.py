"""Command-line argument parsing, validation, and generation orchestration."""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from math import isfinite
from pathlib import Path
from time import perf_counter

from openai import OpenAI

from . import estimates
from .audio import generate_audio_files
from .config import (
    DEFAULT_MODEL,
    DEFAULT_RESPONSE_FORMAT,
    DEFAULT_VOICE,
    OUTPUT_DIR,
    RESPONSE_FORMATS,
    VOICES,
)
from .errors import CliError
from .models import uses_character_billing
from .reporting import print_estimate, print_summary
from .text_input import resolve_text
from .voices import available_voices, resolve_voices


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
        if uses_character_billing(args.model):
            raise SystemExit(f"--instructions is not supported by {args.model}.")


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
    input_tokens = estimates.validate_text(text, args.model, args.instructions)

    if args.dry_run:
        print_estimate(
            text=text, voices=voices, model=args.model, instructions=args.instructions
        )
        return

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    token_price = estimates.usd_per_1m_input_tokens(args.model)

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
