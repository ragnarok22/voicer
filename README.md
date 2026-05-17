# voicer

Generate OpenAI text-to-speech MP3 files from an interactive prompt.

## Setup

Create a `.env` file or export the variable in your shell:

```sh
OPENAI_API_KEY=your_api_key_here
```

Optional:

```sh
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_USD_PER_1M_TOKENS=0.60
```

## Run

```sh
uv run --env-file .env python main.py
```

Select one or more voices, paste the text, then submit an empty line. Files are written to `outputs/` as:

```text
<text-derived-name>-<voice>-<YYYYMMDD-HHMMSS>.mp3
```

The default model is `gpt-4o-mini-tts`. Override it with `OPENAI_TTS_MODEL` if needed.
After generation, the script prints estimated input tokens, estimated cost, and total elapsed time.
