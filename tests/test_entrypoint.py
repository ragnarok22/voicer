import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("entrypoint", ["console", "script", "module"])
@pytest.mark.parametrize(
    ("arguments", "code", "expected"),
    [
        (["--help"], 0, "--instructions"),
        (["--version"], 0, "voicer 0.2.0"),
        (["--list-voices"], 0, "13. onyx"),
        (["--list-voices", "--model", "tts-1"], 0, "11. fable"),
        (["--invalid-option"], 2, "unrecognized arguments"),
        (["Hello"], 1, "Set OPENAI_API_KEY"),
    ],
)
def test_cli_entrypoints_outside_repository(
    tmp_path, entrypoint, arguments, code, expected
):
    # Entry points must work independently of pytest's pythonpath=["."].
    if entrypoint == "console":
        executable = Path(sys.executable).parent / (
            "voicer.exe" if os.name == "nt" else "voicer"
        )
        command = [str(executable)]
    elif entrypoint == "script":
        script = Path(__file__).resolve().parent.parent / "main.py"
        command = [sys.executable, str(script)]
    else:
        command = [sys.executable, "-m", "voicer"]
    result = subprocess.run(
        [*command, *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == code
    assert expected in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
