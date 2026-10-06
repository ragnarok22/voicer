"""Model-family detection shared by validation, voices, and pricing."""

import re


def uses_character_billing(model: str) -> bool:
    return (
        re.fullmatch(r"tts-1(?:-hd)?(?:-[0-9]{4}(?:-[0-9]{2}-[0-9]{2})?)?", model)
        is not None
    )
