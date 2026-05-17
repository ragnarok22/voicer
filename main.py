from datetime import datetime
import os
from pathlib import Path
import re
from time import perf_counter

from openai import OpenAI
import tiktoken


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
)
DEFAULT_MODEL = "gpt-4o-mini-tts"
OUTPUT_DIR = Path("outputs")
USD_PER_1M_INPUT_TOKENS = {
    "gpt-4o-mini-tts": 0.60,
}


def read_text() -> str:
    print("Paste the text to turn into audio. Submit an empty line when finished.")
    lines: list[str] = []

    while True:
        line = input()
        if not line:
            break
        lines.append(line)

    text = "\n".join(lines).strip()
    if not text:
        raise SystemExit("No text provided.")

    return text


def select_voices() -> list[str]:
    print("Available voices:")
    for index, voice in enumerate(VOICES, start=1):
        print(f"  {index}. {voice}")

    raw_selection = input(
        "Select voices by number/name, comma-separated, or 'all' [alloy]: "
    ).strip()
    if not raw_selection:
        return ["alloy"]
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

        raise SystemExit(f"Unknown voice selection: {item.strip()}")

    selected = list(dict.fromkeys(selected))
    if not selected:
        raise SystemExit("No voices selected.")

    return selected


def filename_base(text: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())[:8]
    return "-".join(words) or "voice"


def count_input_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")

    return len(encoding.encode(text))


def usd_per_1m_input_tokens(model: str) -> float | None:
    raw_price = os.environ.get("OPENAI_TTS_USD_PER_1M_TOKENS")
    if raw_price is None:
        return USD_PER_1M_INPUT_TOKENS.get(model)

    try:
        return float(raw_price)
    except ValueError:
        raise SystemExit("OPENAI_TTS_USD_PER_1M_TOKENS must be a number.") from None


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running this script.")

    voices = select_voices()
    text = read_text()
    model = os.environ.get("OPENAI_TTS_MODEL", DEFAULT_MODEL)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_tokens = count_input_tokens(text, model)
    total_input_tokens = input_tokens * len(voices)
    token_price = usd_per_1m_input_tokens(model)

    client = OpenAI()
    OUTPUT_DIR.mkdir(exist_ok=True)
    total_start = perf_counter()
    generated_files: list[Path] = []

    for voice in voices:
        output_path = OUTPUT_DIR / f"{filename_base(text)}-{voice}-{timestamp}.mp3"
        file_start = perf_counter()
        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(output_path)
        generated_files.append(output_path)
        print(f"Generated {output_path} in {format_seconds(perf_counter() - file_start)}")

    total_elapsed = perf_counter() - total_start
    print("\nSummary")
    print(f"Files generated: {len(generated_files)}")
    print(
        "Estimated input tokens: "
        f"{total_input_tokens:,} ({input_tokens:,} per file x {len(voices)})"
    )
    if token_price is None:
        print("Estimated cost: unavailable for this model")
        print("Set OPENAI_TTS_USD_PER_1M_TOKENS to calculate it.")
    else:
        estimated_cost = total_input_tokens / 1_000_000 * token_price
        print(f"Estimated cost: ${estimated_cost:.6f} USD")
        print(f"Price used: ${token_price:g} USD per 1M input tokens")
    print(f"Total time: {format_seconds(total_elapsed)}")


if __name__ == "__main__":
    main()
