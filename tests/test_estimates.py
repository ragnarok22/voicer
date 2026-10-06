from pathlib import Path

import pytest

from voicer import estimates, reporting
from voicer.config import DEFAULT_MODEL


@pytest.fixture(autouse=True)
def isolated_estimation(monkeypatch):
    monkeypatch.delenv("OPENAI_TTS_USD_PER_1M_TOKENS", raising=False)

    def count_tokens(text: str, model: str) -> int:
        return len(text.split())

    monkeypatch.setattr(estimates, "count_input_tokens", count_tokens)


@pytest.mark.parametrize("instructions", [None, "", "Speak very slowly"])
def test_estimate_counts_text_and_instructions_per_voice(
    monkeypatch, capsys, instructions: str | None
) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", "2")
    calls: list[tuple[str, str]] = []

    def count_tokens(text: str, model: str) -> int:
        calls.append((text, model))
        return len(text.split())

    monkeypatch.setattr(estimates, "count_input_tokens", count_tokens)
    reporting.print_estimate(
        text="Hello world",
        voices=["marin", "cedar", "alloy"],
        model=DEFAULT_MODEL,
        instructions=instructions,
    )

    per_file = 5 if instructions else 2
    total = per_file * 3
    output = capsys.readouterr().out
    assert f"Estimated input tokens: {total} ({per_file} per file x 3)" in output
    assert f"Estimated text input cost: ${total * 2 / 1_000_000:.6f} USD" in output
    assert "Excludes generated audio cost; this estimate is not a bill." in output
    assert calls == [("Hello world", DEFAULT_MODEL)] + (
        [(instructions, DEFAULT_MODEL)] if instructions else []
    )
    if instructions:
        assert "conservative" in output
        assert "not exact billed usage" in output


@pytest.mark.parametrize(("tokens", "price"), [(0, 2.0), (100, 0.0), (0, 0.0)])
def test_zero_tokens_or_price_has_zero_text_cost(tokens: int, price: float) -> None:
    assert estimates.format_cost(tokens, price)[0] == (
        "Estimated text input cost: $0.000000 USD"
    )


@pytest.mark.parametrize("price", ["0", " 1.25 ", "2e-1"])
def test_valid_environment_prices(monkeypatch, price: str) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    assert estimates.usd_per_1m_input_tokens(DEFAULT_MODEL) == float(price)


@pytest.mark.parametrize("price", ["", " ", "not-a-number", "1,25"])
def test_malformed_price_preserves_error_message(monkeypatch, price: str) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    with pytest.raises(SystemExit) as error:
        estimates.usd_per_1m_input_tokens(DEFAULT_MODEL)
    assert str(error.value) == "OPENAI_TTS_USD_PER_1M_TOKENS must be a number."


@pytest.mark.parametrize("price", ["-1", "nan", "inf", "-inf", "1e999"])
def test_invalid_environment_price_stops_estimate(monkeypatch, capsys, price: str):
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    with pytest.raises(SystemExit, match="finite.*non-negative"):
        reporting.print_estimate(text="Hello", voices=["marin"], model=DEFAULT_MODEL)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("price", [-1.0, float("nan"), float("inf"), -float("inf")])
def test_format_cost_rejects_invalid_direct_prices(price: float) -> None:
    with pytest.raises(SystemExit, match="finite.*non-negative"):
        estimates.format_cost(100, price)


@pytest.mark.parametrize("model", ["tts-1", "tts-1-hd", "tts-1-1106", "tts-1-hd-1106"])
@pytest.mark.parametrize("price", [None, "0.6", "not-a-number", "nan"])
def test_legacy_models_never_apply_token_prices(monkeypatch, capsys, model, price):
    if price is not None:
        monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    assert estimates.usd_per_1m_input_tokens(model) is None
    lines = estimates.format_cost(1_000_000, 2.0, model=model)
    assert lines[0] == "Estimated text input cost: unavailable"
    assert f"{model} uses character-based billing; no token price applies." in lines
    assert not any("Set OPENAI_TTS_USD_PER_1M_TOKENS" in line for line in lines)

    reporting.print_estimate(text="Hello world", voices=["marin", "cedar"], model=model)
    output = capsys.readouterr().out
    assert "character-based billing; no token price applies." in output
    assert "Price used:" not in output
    assert "Estimated text input cost: $" not in output


@pytest.mark.parametrize("model", ["unknown-model", "tts-1-custom"])
@pytest.mark.parametrize("price", [None, "2"])
def test_unknown_model_requires_explicit_token_price(monkeypatch, capsys, model, price):
    if price is not None:
        monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", price)
    assert estimates.usd_per_1m_input_tokens(model) == (2.0 if price else None)
    reporting.print_estimate(text="Hello world", voices=["marin"], model=model)
    output = capsys.readouterr().out
    if price:
        assert "Estimated text input cost: $0.000004 USD" in output
    else:
        assert "Estimated text input cost: unavailable" in output
        assert "Set OPENAI_TTS_USD_PER_1M_TOKENS" in output
    assert "character-based billing" not in output


@pytest.mark.parametrize("model", [DEFAULT_MODEL, "tts-1-hd-1106"])
def test_summary_uses_model_and_per_file_estimated_tokens(capsys, model: str) -> None:
    reporting.print_summary(
        generated_files=[Path("marin.mp3"), Path("cedar.mp3")],
        input_tokens=5,
        voices=["marin", "cedar"],
        token_price=2.0,
        total_elapsed=1.234,
        model=model,
    )
    output = capsys.readouterr().out
    assert "Files generated: 2" in output
    assert "Estimated input tokens: 10 (5 per file x 2)" in output
    assert "Total time: 1.23s" in output
    assert "Excludes generated audio cost; this estimate is not a bill." in output
    if model == DEFAULT_MODEL:
        assert "Estimated text input cost: $0.000020 USD" in output
    else:
        assert "character-based billing; no token price applies." in output
        assert "Price used:" not in output


def test_summary_keeps_existing_call_signature(capsys) -> None:
    reporting.print_summary(
        generated_files=[],
        input_tokens=0,
        voices=[],
        token_price=None,
        total_elapsed=0,
    )
    output = capsys.readouterr().out
    assert "Estimated input tokens: 0 (0 per file x 0)" in output
    assert "Estimated text input cost: unavailable" in output
