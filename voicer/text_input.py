"""Read text from arguments, UTF-8 files, stdin, or an interactive prompt."""

import sys
from pathlib import Path
from typing import TextIO


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
