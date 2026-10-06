# voicer

[![CI](https://github.com/ragnarok22/voicer/actions/workflows/ci.yml/badge.svg)](https://github.com/ragnarok22/voicer/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Managed with uv](https://img.shields.io/badge/managed_with-uv-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Linting and formatting with Ruff](https://img.shields.io/badge/lint_%26_format-Ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![Type checked with ty](https://img.shields.io/badge/type_checked-ty-DE5FE9)](https://docs.astral.sh/ty/)

Generate OpenAI text-to-speech audio from a small, practical CLI.

`voicer` accepts text from an argument, file, stdin, or an interactive prompt, then writes audio files for one or more OpenAI voices.

## Requirements

- Python 3.14+
- `uv`
- An OpenAI API key with access to the audio speech API

## Setup

Create a `.env` file:

```sh
OPENAI_API_KEY=your_api_key_here
```

Optional settings:

```sh
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_USD_PER_1M_TOKENS=your_current_price_per_1m_input_tokens
```

`OPENAI_TTS_USD_PER_1M_TOKENS` is only needed for cost estimates. Pricing changes over time, so `voicer` does not assume a default price.

## Quickstart

```sh
uv run --env-file .env voicer "Hello from voicer"
```

By default, this uses the `marin` voice, the `gpt-4o-mini-tts` model, and writes an MP3 to `outputs/`.

## Input Methods

Pass text directly:

```sh
uv run --env-file .env voicer "Ladies and gentlemen, welcome aboard."
```

Read text from a file:

```sh
uv run --env-file .env voicer --file announcement.txt
```

Pipe text from another command:

```sh
printf "Hello from stdin" | uv run --env-file .env voicer
```

Open the interactive prompt:

```sh
uv run --env-file .env voicer
```

In interactive mode, paste your text and submit an empty line to start generation.

## Voices

List available voices:

```sh
uv run voicer --list-voices
```

Use one voice:

```sh
uv run --env-file .env voicer --voice marin "Hola a todos"
```

Use multiple voices:

```sh
uv run --env-file .env voicer --voice marin --voice echo "Compare these voices"
uv run --env-file .env voicer --voice marin,echo,alloy "Compare these voices"
```

Generate every supported voice:

```sh
uv run --env-file .env voicer --voice all --file script.txt
```

Voice selections also accept numbers from `--list-voices`.

## Output

Generated files are written to `outputs/` by default:

```text
<text-derived-name>-<voice>-<YYYYMMDD-HHMMSS>.<format>
```

Choose a different output directory:

```sh
uv run --env-file .env voicer --output-dir audio "Hello"
```

Choose an exact output path for a single voice:

```sh
uv run --env-file .env voicer --output greeting.mp3 "Hello"
```

`--output` refuses to overwrite existing files unless you pass `--force`:

```sh
uv run --env-file .env voicer --output greeting.mp3 --force "Hello again"
```

## Formats And Models

Set the audio format:

```sh
uv run --env-file .env voicer --format wav "Save this as WAV"
```

Supported formats are `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`.

Use another model:

```sh
uv run --env-file .env voicer --model gpt-4o-mini-tts "Hello"
```

You can also set `OPENAI_TTS_MODEL` in `.env`.

## Estimates

Preview token usage and cost without calling OpenAI:

```sh
uv run voicer --dry-run --voice marin,echo "Estimate this first"
```

If `OPENAI_TTS_USD_PER_1M_TOKENS` is set, `--dry-run` and generation summaries include an estimated input-token cost.

## CLI Reference

```text
usage: voicer [-h] [-f INPUT_FILE] [--stdin] [-v VOICE_SELECTIONS]
              [--list-voices] [-m MODEL]
              [--format {mp3,opus,aac,flac,wav,pcm}] [-o OUTPUT_FILE]
              [--output-dir OUTPUT_DIR] [--force] [--dry-run] [--version]
              [text]
```

Common flags:

```text
--voice, -v       Voice name, number, comma-list, or all. Repeatable. Default: marin.
--file, -f        Read text from a UTF-8 file.
--stdin           Read text from stdin explicitly.
--output-dir      Directory for generated files. Default: outputs.
--output, -o      Exact output file path. Only valid with one voice.
--force           Overwrite --output if it already exists.
--format          mp3, opus, aac, flac, wav, or pcm. Default: mp3.
--model, -m       OpenAI TTS model. Default: OPENAI_TTS_MODEL or gpt-4o-mini-tts.
--dry-run         Print token and cost estimates without calling OpenAI.
--list-voices     Print supported voices and exit.
--version         Print the installed version.
```

Run the full help output with:

```sh
uv run voicer --help
```

## Development

Use the Makefile to run development tools through `uv`:

```sh
make help          # List available commands (also the default for make)
make format        # Format Python code with Ruff
make format-check  # Check formatting without changing files
make lint          # Fix auto-fixable lint issues with Ruff
make lint-check    # Check Python code with Ruff without changing files
make typecheck     # Check Python types with ty
make test          # Run tests with pytest
```

## Continuous Integration

GitHub Actions runs formatting, lint, type, and test checks in parallel on every
push and pull request. The workflow can also be started manually from the Actions
tab. It uses the Python version in `.python-version` and installs development
dependencies from `uv.lock`, failing if the lockfile is out of date.

Run the same checks locally:

```sh
uv sync --locked --group dev
make format-check lint-check typecheck test
```
