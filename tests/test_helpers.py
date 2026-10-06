import pytest

from voicer import estimates
from voicer.audio import filename_base
from voicer.estimates import format_cost, usd_per_1m_input_tokens
from voicer.reporting import format_seconds


@pytest.fixture(autouse=True)
def offline_tokenizer_resources(monkeypatch) -> None:
    def unexpected_resource_load(*args, **kwargs):
        pytest.fail("Tokenizer tests must provide in-memory encoding resources")

    monkeypatch.setattr(
        estimates.tiktoken, "encoding_for_model", unexpected_resource_load
    )
    monkeypatch.setattr(estimates.tiktoken, "get_encoding", unexpected_resource_load)


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
        "Estimated text input cost: unavailable",
        "Set OPENAI_TTS_USD_PER_1M_TOKENS to estimate text input cost.",
        "Excludes generated audio cost; this estimate is not a bill.",
    ]


def test_format_cost_calculates_from_configured_price() -> None:
    assert format_cost(2500, 2.0) == [
        "Estimated text input cost: $0.005000 USD",
        "Price used: $2 USD per 1M text input tokens",
        "Excludes generated audio cost; this estimate is not a bill.",
    ]


def test_usd_per_1m_input_tokens_returns_none_without_price_override(
    monkeypatch,
) -> None:
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
        def encode_ordinary(self, text: str) -> list[str]:
            return text.split()

    def encoding_for_model(model: str) -> Encoding:
        assert model == "known-model"
        return Encoding()

    monkeypatch.setattr(estimates.tiktoken, "encoding_for_model", encoding_for_model)

    assert estimates.count_input_tokens("one two three", "known-model") == 3


def test_count_input_tokens_falls_back_for_unknown_model(monkeypatch) -> None:
    class Encoding:
        def encode_ordinary(self, text: str) -> list[str]:
            return list(text)

    def encoding_for_model(model: str) -> Encoding:
        assert model == "unknown-model"
        raise KeyError(model)

    def get_encoding(name: str) -> Encoding:
        assert name == "o200k_base"
        return Encoding()

    monkeypatch.setattr(estimates.tiktoken, "encoding_for_model", encoding_for_model)
    monkeypatch.setattr(estimates.tiktoken, "get_encoding", get_encoding)

    assert estimates.count_input_tokens("abc", "unknown-model") == 3


@pytest.mark.parametrize("model", ["known-model", "unknown-model"])
@pytest.mark.parametrize(
    "text",
    ["<|endoftext|>", "Read <|endoftext|> aloud.", "Café <|endoftext|> 🙂"],
)
def test_count_input_tokens_treats_special_literals_as_ordinary_text(
    monkeypatch, model: str, text: str
) -> None:
    # Real tiktoken behavior, with a fabricated byte vocabulary: no cache or downloads.
    encoding = estimates.tiktoken.Encoding(
        "test-byte-encoding",
        pat_str=r"(?s:.)",
        mergeable_ranks={bytes([byte]): byte for byte in range(256)},
        special_tokens={"<|endoftext|>": 256},
    )

    def encoding_for_model(name: str):
        assert name == model
        if name == "unknown-model":
            raise KeyError(name)
        return encoding

    def get_encoding(name: str):
        assert name == "o200k_base"
        assert model == "unknown-model"
        return encoding

    monkeypatch.setattr(estimates.tiktoken, "encoding_for_model", encoding_for_model)
    monkeypatch.setattr(estimates.tiktoken, "get_encoding", get_encoding)

    assert estimates.count_input_tokens(text, model) == len(text.encode("utf-8"))
