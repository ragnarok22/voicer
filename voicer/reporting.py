"""Console estimates, generation summaries, and elapsed-time formatting."""

from pathlib import Path

from . import estimates
from .config import DEFAULT_MODEL


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def print_estimate(
    *,
    text: str,
    voices: list[str],
    model: str,
    instructions: str | None = None,
) -> None:
    input_tokens = estimates.count_input_tokens(text, model)
    if instructions:
        input_tokens += estimates.count_input_tokens(instructions, model)
    total_input_tokens = input_tokens * len(voices)
    token_price = estimates.usd_per_1m_input_tokens(model)

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
    for line in estimates.format_cost(total_input_tokens, token_price, model=model):
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
    for line in estimates.format_cost(total_input_tokens, token_price, model=model):
        print(line)
    print(f"Total time: {format_seconds(total_elapsed)}")
