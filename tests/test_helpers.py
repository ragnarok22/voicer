import pytest

import main
from main import filename_base, format_cost, format_seconds, usd_per_1m_input_tokens


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello, world! This is a test.", "hello-world-this-is-a-test"),
        (
            "One two three four five six seven eight nine",
            "one-two-three-four-five-six-seven-eight",
        ),
        ("!!!", "voice"),
        ("Cafe 123 -- VOICE", "cafe-123-voice"),
    ],
)
def test_filename_base_normalizes_text(text: str, expected: str) -> None:
    assert filename_base(text) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0.00s"),
        (1.234, "1.23s"),
        (12.999, "13.00s"),
    ],
)
def test_format_seconds_uses_two_decimal_places(seconds: float, expected: str) -> None:
    assert format_seconds(seconds) == expected


def test_format_cost_is_unavailable_without_configured_price() -> None:
    assert format_cost(1000, None) == [
        "Estimated cost: unavailable",
        "Set OPENAI_TTS_USD_PER_1M_TOKENS to calculate it.",
    ]


def test_format_cost_calculates_from_configured_price() -> None:
    assert format_cost(2500, 2.0) == [
        "Estimated cost: $0.005000 USD",
        "Price used: $2 USD per 1M input tokens",
    ]


def test_usd_per_1m_input_tokens_returns_none_without_price_override(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TTS_USD_PER_1M_TOKENS", raising=False)

    assert usd_per_1m_input_tokens("gpt-4o-mini-tts") is None


def test_usd_per_1m_input_tokens_uses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", "1.25")

    assert usd_per_1m_input_tokens("custom-model") == 1.25


def test_usd_per_1m_input_tokens_rejects_invalid_override(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TTS_USD_PER_1M_TOKENS", "not-a-number")

    with pytest.raises(SystemExit) as exc_info:
        usd_per_1m_input_tokens("gpt-4o-mini-tts")

    assert str(exc_info.value) == "OPENAI_TTS_USD_PER_1M_TOKENS must be a number."


def test_count_input_tokens_uses_model_encoding(monkeypatch) -> None:
    class Encoding:
        def encode(self, text: str) -> list[str]:
            return text.split()

    def encoding_for_model(model: str) -> Encoding:
        assert model == "known-model"
        return Encoding()

    monkeypatch.setattr(main.tiktoken, "encoding_for_model", encoding_for_model)

    assert main.count_input_tokens("one two three", "known-model") == 3


def test_count_input_tokens_falls_back_for_unknown_model(monkeypatch) -> None:
    class Encoding:
        def encode(self, text: str) -> list[str]:
            return list(text)

    def encoding_for_model(model: str) -> Encoding:
        assert model == "unknown-model"
        raise KeyError(model)

    def get_encoding(name: str) -> Encoding:
        assert name == "o200k_base"
        return Encoding()

    monkeypatch.setattr(main.tiktoken, "encoding_for_model", encoding_for_model)
    monkeypatch.setattr(main.tiktoken, "get_encoding", get_encoding)

    assert main.count_input_tokens("abc", "unknown-model") == 3
