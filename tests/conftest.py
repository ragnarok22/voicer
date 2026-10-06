import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "OPENAI_PROJECT_ID",
        "OPENAI_TTS_MODEL",
        "OPENAI_TTS_USD_PER_1M_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)

    def unexpected_network(*args, **kwargs):
        pytest.fail("Tests must not connect to the network")

    monkeypatch.setattr(socket.socket, "connect", unexpected_network)
    monkeypatch.setattr(socket.socket, "connect_ex", unexpected_network)
