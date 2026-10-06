# Repository instructions

## Commands

- Use `uv` with Python 3.14+; `.python-version` pins the interpreter used locally and in CI. Setup: `uv sync --locked --group dev`.
- `make check` runs Ruff formatting checks, Ruff lint checks, `ty`, then pytest with branch coverage. CI runs these same targets independently. Coverage for `voicer` must reach 90%.
- Focused tests: `make test TEST_ARGS="tests/test_audio.py -q"`; a single test: `make test TEST_ARGS="tests/test_tts_cli.py::test_current_catalog_preserves_voice_numbers -q"`. Use `make coverage` for the full coverage gate; focused coverage still applies the package-wide threshold.
- `make lint` **modifies files** (`ruff check --fix`); use `make lint-check` for verification. Likewise, `make format` modifies files and `make format-check` checks them. All tool targets use `uv run --locked`.
- The app does not load `.env` itself: run generation with `uv run --env-file .env voicer "Hello"`. `uv run voicer --list-voices` and `--completion bash` require no credentials or network; `--dry-run` needs no API key but tiktoken may download encoding data on first use.

## Wiring and compatibility

- The installed command, `main.py`, and `python -m voicer` all delegate to `voicer.cli:cli`. `cli.main(argv)` takes explicit arguments (default: empty); only `cli()` reads `sys.argv` and translates Ctrl+C into a CLI error.
- Shell completion is generated at runtime from `cli.build_parser()`, not checked-in scripts. Special voice/model suggestions live in `voicer/completion.py`; known model suggestions must not restrict the open-ended `--model` argument. Completions register for `voicer`, not `uv run voicer`.
- `config.VOICES` order defines stable, one-based public voice numbers. Append new voices rather than reorder existing entries; model-filtered listings retain global numbers.
- Model-family detection in `voicer/models.py` is shared by voice compatibility, instruction validation, and pricing. Preserve support for dated legacy models and mini-TTS snapshots when changing model behavior.
- Version text is duplicated in `pyproject.toml` and `cli.build_parser()`; `tests/test_entrypoint.py` also asserts it.

## Streaming and tests

- The OpenAI SDK uses **`httpx2`**, not `httpx`. SDK integration tests inject `httpx2.MockTransport` into real `openai.OpenAI` clients; see `tests/test_tts_cli.py`.
- `tests/conftest.py` clears OpenAI-related environment settings and blocks socket connections. Tokenizer-dependent tests stub token counting/encoding to stay offline; new tests must not rely on an encoding cache or real API credentials.
- Completion integration tests execute Bash, Zsh, and Fish and skip missing shells; CI installs all three. Preserve Bash 3.2 compatibility (macOS lacks `compopt`).
- `audio.generate_audio_files()` preflights and reserves same-directory temporary files for **all** destinations before the first speech request. Publish only after both writer and response close successfully; retain race-safe no-overwrite publication and clean up on errors or cancellation, including with `--force`.
- Generation is sequential: if a later voice fails, earlier completed files remain. Streaming failures are not replayed automatically; retries are handled by the SDK before streaming starts.
