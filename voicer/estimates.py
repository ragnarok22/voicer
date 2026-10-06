"""Token counting, speech input limits, and configured text-cost estimates."""

import os
from math import isfinite

import tiktoken

from .config import DEFAULT_MODEL, MAX_INPUT_CHARACTERS, MINI_MAX_INPUT_TOKENS
from .models import uses_character_billing


def count_input_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")

    return len(encoding.encode_ordinary(text))


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


def usd_per_1m_input_tokens(model: str) -> float | None:
    if uses_character_billing(model):
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


def format_cost(
    total_input_tokens: int,
    token_price: float | None,
    *,
    model: str = DEFAULT_MODEL,
) -> list[str]:
    disclaimer = "Excludes generated audio cost; this estimate is not a bill."
    if uses_character_billing(model):
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
