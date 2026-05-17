# voicer

Generate OpenAI text-to-speech audio from a practical CLI.

## Setup

Create a `.env` file or export the variable in your shell:

```sh
OPENAI_API_KEY=your_api_key_here
```

Optional:

```sh
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_USD_PER_1M_TOKENS=your_current_price_per_1m_input_tokens
```

Set `OPENAI_TTS_USD_PER_1M_TOKENS` when you want cost estimates; pricing changes over time, so `voicer` does not assume a default price.

## Usage

```sh
uv run --env-file .env voicer "Hello from voicer"
```

You can also pipe text, read a file, or use the interactive prompt:

```sh
printf "Hello from stdin" | uv run --env-file .env voicer
uv run --env-file .env voicer --file script.txt
uv run --env-file .env voicer
```

Files are written to `outputs/` as:

```text
<text-derived-name>-<voice>-<YYYYMMDD-HHMMSS>.<format>
```

## Options

```sh
uv run voicer --list-voices
uv run --env-file .env voicer --voice alloy --voice echo "Hello"
uv run --env-file .env voicer --voice all --format wav --file announcement.txt
uv run voicer --dry-run --voice marin "Estimate this first"
uv run --env-file .env voicer --output greeting.mp3 --force "Hello"
```

Useful flags:

```text
--voice, -v       Voice name, number, comma-list, or all. Repeatable. Default: alloy.
--file, -f        Read text from a UTF-8 file.
--stdin           Read text from stdin explicitly.
--output-dir      Directory for generated files. Default: outputs.
--output, -o      Exact output file path. Only valid with one voice.
--format          mp3, opus, aac, flac, wav, or pcm. Default: mp3.
--model, -m       OpenAI TTS model. Default: OPENAI_TTS_MODEL or gpt-4o-mini-tts.
--dry-run         Print token and cost estimates without calling OpenAI.
--list-voices     Print supported voices.
```

After generation, `voicer` prints estimated input tokens, estimated cost when configured, and total elapsed time.
