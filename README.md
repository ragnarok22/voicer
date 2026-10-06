# voicer

[![CI](https://img.shields.io/github/actions/workflow/status/ragnarok22/voicer/ci.yml?label=CI&logo=github)](https://github.com/ragnarok22/voicer/actions/workflows/ci.yml)
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

Install the locked dependencies, copy `.env.example` to `.env`, and set your API key:

```sh
uv sync --locked
cp .env.example .env
```

The `.env` file should contain:

```sh
OPENAI_API_KEY=your_api_key_here
```

Optional settings:

```sh
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_USD_PER_1M_TOKENS=your_current_price_per_1m_input_tokens
```

`OPENAI_TTS_USD_PER_1M_TOKENS` is only needed for **text input** cost estimates. Pricing changes over time, so `voicer` does not assume a default price. This estimate excludes generated audio output costs.

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

In interactive mode, paste your text and submit an empty line or EOF to start generation. Press Ctrl+C to cancel.

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

The current built-in catalog contains `alloy`, `ash`, `ballad`, `coral`, `echo`,
`sage`, `shimmer`, `verse`, `marin`, `cedar`, `fable`, `nova`, and `onyx`.
Existing voice numbers are preserved; the three additional voices are 11–13.

`--list-voices` and `--voice all` use the selected model's supported voices:

```sh
uv run voicer --model tts-1 --list-voices
```

`tts-1` and `tts-1-hd` support `alloy`, `ash`, `coral`, `echo`, `fable`, `nova`,
`onyx`, `sage`, and `shimmer`. Their default voice is `alloy`; explicitly selecting
an incompatible voice is rejected before generation.

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

Each download is staged in a temporary file in the destination directory and
published only after the stream completes. Failed downloads and cancellations
remove temporary files and preserve existing audio, including with `--force`.
All destinations are checked before the first request. If a later voice fails,
files already completed for earlier voices remain available.

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

`gpt-4o-mini-tts` uses OpenAI's current alias. To select a documented snapshot:

```sh
uv run --env-file .env voicer --model gpt-4o-mini-tts-2025-12-15 "Hello"
```

Model names remain open-ended to allow new models; local model-specific checks
cover known model families. Availability and account access are determined by OpenAI.

## Style, Speed And Request Controls

Control style and speed:

```sh
uv run --env-file .env voicer --voice cedar \
  --instructions "Speak warmly, with a calm pace and a Spanish accent." \
  --speed 0.9 "Hola, bienvenidos a bordo."
```

`--speed` accepts finite values from `0.25` to `4.0`, with `1.0` as the default.
`--instructions` must contain text and is not supported by `tts-1` or `tts-1-hd`.

Configure request handling:

```sh
uv run --env-file .env voicer --timeout 60 --max-retries 0 "Hello"
```

The default timeout is 600 seconds per request and the SDK allows two retries.
`--timeout` must be finite and positive; `--max-retries` must be a non-negative
integer. Eligible failures may be retried before the audio stream starts. An
interrupted download is not replayed automatically.

## Input Limits

The Speech endpoint accepts at most **4096 characters** per input. For
`gpt-4o-mini-tts` and its snapshots, the CLI also checks the documented
**2000-input-token** limit using a local token estimate, including instructions
conservatively. Exact server tokenization and billing may differ.

Oversized inputs produce an error before generation, including during `--dry-run`.
Provide shorter text or instructions; automatic splitting and concatenation are
not implemented.

## Estimates

Preview token usage and cost without calling OpenAI:

```sh
uv run voicer --dry-run --voice marin,echo "Estimate this first"
```

If `OPENAI_TTS_USD_PER_1M_TOKENS` is set to a finite, non-negative price,
`--dry-run` and generation summaries include an **estimated text input cost**.
Text and instruction tokens are estimated per file and multiplied by the number
of voices. This is a partial estimate, not a bill or a total generation cost:
generated audio output is excluded.

`tts-1` and `tts-1-hd` use character-based billing, so their cost is reported as
unavailable and the token-price setting is ignored. Unknown models use that
setting only as an explicit user-provided assumption.

The tokenizer may download its encoding data on first use. `--dry-run` never
sends your text to OpenAI or requires an API key; `--list-voices` needs neither
tokenization nor API access.

## CLI Reference

```text
usage: voicer [-h] [-f INPUT_FILE] [--stdin] [-v VOICE_SELECTIONS]
              [--list-voices] [-m MODEL] [--instructions INSTRUCTIONS]
              [--speed SPEED] [--timeout TIMEOUT] [--max-retries MAX_RETRIES]
              [--format {mp3,opus,aac,flac,wav,pcm}] [-o OUTPUT_FILE]
              [--output-dir OUTPUT_DIR] [--force] [--dry-run] [--version]
              [text]
```

Common flags:

```text
--voice, -v       Voice name, number, comma-list, or all. Default: marin; alloy for legacy models.
--file, -f        Read text from a UTF-8 file.
--stdin           Read text from stdin explicitly.
--output-dir      Directory for generated files. Default: outputs.
--output, -o      Exact output file path. Only valid with one voice.
--force           Overwrite --output if it already exists.
--format          mp3, opus, aac, flac, wav, or pcm. Default: mp3.
--model, -m       OpenAI TTS model. Default: OPENAI_TTS_MODEL or gpt-4o-mini-tts.
--instructions    Voice style instructions; unavailable for tts-1/tts-1-hd.
--speed           Speech speed, 0.25–4.0. Default: 1.0.
--timeout         Positive request timeout in seconds. Default: 600.
--max-retries     Non-negative SDK retry count. Default: 2.
--dry-run         Print token and cost estimates without calling OpenAI.
--list-voices     Print supported voices for the selected model and exit.
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
make coverage      # Run tests with branch coverage and XML report
make check         # Run all non-mutating verification checks
```

Use `make test TEST_ARGS="tests/test_audio.py -q"` for a focused run. Coverage
checks enforce a 90% minimum for `main.py`, including branches. Tests use the
real OpenAI SDK with mocked HTTPX2 transport and block socket connections;
they require no credentials or paid API calls.

## Continuous Integration

GitHub Actions runs formatting, lint, type, and test/coverage checks in parallel on every
push and pull request. The workflow can also be started manually from the Actions
tab. It uses the Python version in `.python-version` and installs development
dependencies from `uv.lock`, failing if the lockfile is out of date.

Run the same checks locally:

```sh
uv sync --locked --group dev
make check
```

## API References

The TTS integration was reviewed against the official documentation on
2026-10-06:

- [Text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- [Speech endpoint reference](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create)
- [GPT-4o mini TTS model and pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
- [OpenAI Python HTTPX2 migration](https://github.com/openai/openai-python/blob/main/httpx2.md)
