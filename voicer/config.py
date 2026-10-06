"""Shared defaults, supported voices, audio formats, and input limits."""

from pathlib import Path
from typing import Literal

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
    "fable",
    "nova",
    "onyx",
)
LEGACY_VOICES = frozenset(
    ("alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer")
)
DEFAULT_MODEL = "gpt-4o-mini-tts"
OUTPUT_DIR = Path("outputs")
DEFAULT_VOICE = "marin"
type ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
DEFAULT_RESPONSE_FORMAT: ResponseFormat = "mp3"
RESPONSE_FORMATS = ("mp3", "opus", "aac", "flac", "wav", "pcm")
MAX_INPUT_CHARACTERS = 4096
MINI_MAX_INPUT_TOKENS = 2000
