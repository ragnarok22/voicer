"""Parse voice selections and filter the catalog for a model."""

from .config import DEFAULT_MODEL, DEFAULT_VOICE, LEGACY_VOICES, VOICES
from .errors import CliError
from .models import uses_character_billing


def parse_voice_selection(
    raw_selection: str,
    *,
    default: str | None = DEFAULT_VOICE,
) -> list[str]:
    raw_selection = raw_selection.strip()
    if not raw_selection:
        if default is None:
            raise CliError("No voices selected.")
        return [default]
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

        raise CliError(f"Unknown voice selection: {item.strip()}")

    selected = list(dict.fromkeys(selected))
    if not selected:
        raise CliError("No voices selected.")

    return selected


def select_voices() -> list[str]:
    print("Available voices:")
    for index, voice in enumerate(VOICES, start=1):
        print(f"  {index}. {voice}")

    raw_selection = input(
        f"Select voices by number/name, comma-separated, or 'all' [{DEFAULT_VOICE}]: "
    )
    try:
        return parse_voice_selection(raw_selection)
    except CliError as error:
        raise SystemExit(str(error)) from error


def available_voices(model: str) -> tuple[str, ...]:
    if uses_character_billing(model):
        return tuple(voice for voice in VOICES if voice in LEGACY_VOICES)
    return VOICES


def resolve_voices(
    selections: list[str] | None, model: str = DEFAULT_MODEL
) -> list[str]:
    if not selections:
        return ["alloy" if uses_character_billing(model) else DEFAULT_VOICE]

    voices: list[str] = []
    for selection in selections:
        if selection.strip().lower() == "all":
            voices.extend(available_voices(model))
        else:
            voices.extend(parse_voice_selection(selection, default=None))

    voices = list(dict.fromkeys(voices))
    unsupported = [voice for voice in voices if voice not in available_voices(model)]
    if unsupported:
        raise CliError(f"Voices not supported by {model}: {', '.join(unsupported)}.")
    return voices
