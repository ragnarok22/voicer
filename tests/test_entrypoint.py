import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("arguments", "code", "expected"),
    [
        (["--help"], 0, "--instructions"),
        (["--version"], 0, "voicer 0.1.0"),
        (["--list-voices"], 0, "13. onyx"),
        (["--list-voices", "--model", "tts-1"], 0, "11. fable"),
        (["--invalid-option"], 2, "unrecognized arguments"),
        (["Hello"], 1, "Set OPENAI_API_KEY"),
    ],
)
def test_installed_entrypoint_outside_repository(tmp_path, arguments, code, expected):
    # Executable installed from [project.scripts], independent of pythonpath=["."].
    executable = Path(sys.executable).parent / (
        "voicer.exe" if os.name == "nt" else "voicer"
    )
    result = subprocess.run(
        [str(executable), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == code
    assert expected in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
