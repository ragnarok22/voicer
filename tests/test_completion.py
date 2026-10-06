import os
import shlex
import shutil
import subprocess

import pytest

from voicer import cli
from voicer.completion import SHELLS, VOICE_CHOICES, generate_completion
from voicer.config import RESPONSE_FORMATS


@pytest.mark.parametrize("shell", SHELLS)
def test_completion_exits_before_generation(shell, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_TTS_MODEL", "")

    def unexpected_run(args):
        pytest.fail("Completion must not validate, read text, or generate audio")

    monkeypatch.setattr(cli, "run", unexpected_run)
    cli.main(["--completion", shell, "--speed", "nan"])

    assert capsys.readouterr().out == generate_completion(cli.build_parser(), shell)


def test_cli_rejects_unknown_shell(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["--completion", "unknown"])

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_generator_rejects_unknown_shell():
    with pytest.raises(ValueError, match="Unsupported shell"):
        generate_completion(cli.build_parser(), "unknown")


@pytest.mark.parametrize("shell", SHELLS)
def test_new_parser_options_are_included(shell):
    parser = cli.build_parser()
    parser.add_argument(
        "--new-option", choices=("first", "second"), help="A new option"
    )

    script = generate_completion(parser, shell)

    assert "new-option" in script
    assert "first" in script
    assert "second" in script


@pytest.fixture
def completion_files(tmp_path):
    paths = {}
    for shell in SHELLS:
        path = tmp_path / ("_voicer" if shell == "zsh" else f"voicer.{shell}")
        path.write_text(
            generate_completion(cli.build_parser(), shell), encoding="utf-8"
        )
        paths[shell] = path
    (tmp_path / "input with spaces.txt").touch()
    (tmp_path / "audio with spaces").mkdir()
    return paths


def run_shell(shell, command, tmp_path):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    return subprocess.run(
        [executable, "-c", command],
        cwd=tmp_path,
        env={**os.environ, "TERM": "xterm", "LC_ALL": "C"},
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )


@pytest.mark.parametrize("shell", SHELLS)
def test_native_shell_syntax(shell, completion_files, tmp_path):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    subprocess.run(
        [executable, "-n", str(completion_files[shell])],
        check=True,
        capture_output=True,
        timeout=15,
    )


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        (["voicer", "--out"], {"--output", "--output-dir"}),
        (["voicer", "-v", "ma"], {"marin"}),
        (["voicer", "--voice", "alloy,ma"], {"alloy,marin"}),
        (["voicer", "--voice", "echo,alloy,ce"], {"echo,alloy,cedar"}),
        (["voicer", "--voice", ""], set(VOICE_CHOICES)),
        (["voicer", "--voice=alloy,ma"], {"--voice=alloy,marin"}),
        (["voicer", "--voice", "=", "alloy,ma"], {"alloy,marin"}),
        (["voicer", "--format", "="], set(RESPONSE_FORMATS)),
        (["voicer", "--format", ""], set(RESPONSE_FORMATS)),
        (["voicer", "-m", "tts"], {"tts-1", "tts-1-hd"}),
        (["voicer", "--completion", ""], set(SHELLS)),
        (["voicer", "--file", "input"], {"input with spaces.txt"}),
        (["voicer", "-o", "input"], {"input with spaces.txt"}),
        (["voicer", "--output-dir", "a"], {"audio with spaces/"}),
        (["voicer", "--output-dir", "input"], set()),
        (["voicer", "--speed", ""], set()),
        (["voicer", "--instructions", "--out"], set()),
        (["voicer", "--unknown=value"], set()),
        (["voicer", "hello"], set()),
        (["voicer", "--", "--out"], set()),
        (["voicer", "--", "--voice", "ma"], set()),
        (["voicer", "--instructions", "--", "--voice", "ma"], {"marin"}),
        (["voicer", "--voice", "echo", "--voice", "ma"], {"marin"}),
        (["voicer", "--format", "wav", "--out"], {"--output", "--output-dir"}),
    ],
)
def test_bash_completions(words, expected, completion_files, tmp_path):
    command = f"""
        source {shlex.quote(str(completion_files["bash"]))}
        COMP_WORDS=({" ".join(shlex.quote(word) for word in words)})
        COMP_CWORD={len(words) - 1}
        _voicer_complete
        if [[ ${{#COMPREPLY[@]}} -gt 0 ]]; then
            printf '%s\\n' "${{COMPREPLY[@]}}"
        fi
    """
    result = run_shell("bash", command, tmp_path)

    assert set(result.stdout.splitlines()) == expected
    assert not result.stderr


@pytest.mark.parametrize("autoload", [False, True])
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("voicer --voice ma", "voicer --voice marin "),
        ("voicer --voice alloy,ma", "voicer --voice alloy,marin "),
        ("voicer --voice=ma", "voicer --voice=marin "),
        ("voicer --voice echo --voice ce", "voicer --voice echo --voice cedar "),
        ("voicer --voice alloy,13", "voicer --voice alloy,13 "),
        ("voicer --voice al", "voicer --voice all"),
        ("voicer --format wa", "voicer --format wav "),
        ("voicer --completion zs", "voicer --completion zsh "),
        ("voicer --file input", r"voicer --file input\ with\ spaces.txt "),
        ("voicer --output-dir audio", r"voicer --output-dir audio\ with\ spaces/"),
    ],
)
def test_zsh_interactive_completion(
    line, expected, autoload, completion_files, tmp_path
):
    # Exercise the real completion widgets, including loading through fpath.
    if autoload:
        load = f"fpath=({shlex.quote(str(tmp_path))} $fpath); autoload -Uz _voicer; compdef _voicer voicer"
    else:
        load = f"source {shlex.quote(str(completion_files['zsh']))}"
    setup = (
        "PROMPT=''; RPROMPT=''; autoload -Uz compinit; compinit -D; "
        f"{load}; "
        "zle -C _voicer_test complete-word _main_complete; "
        "_voicer_capture() { zle _voicer_test; "
        "print -r -- \"__RESULT__${BUFFER}__END__\"; BUFFER=''; }; "
        "zle -N _voicer_capture; bindkey '^X' _voicer_capture; "
        "print -r -- '__''READY__'"
    )
    command = f"""
        zmodload zsh/zpty
        zpty session zsh -f
        zpty -w session {shlex.quote(setup)}
        zpty -r -m session output '*__READY__*'
        zpty -w -n session {shlex.quote(line)}$'\\x18'
        zpty -r -m session output '*__END__*'
        print -r -- "$output"
        zpty -d session
    """
    result = run_shell("zsh", command, tmp_path)

    assert f"__RESULT__{expected}__END__" in result.stdout
    assert not result.stderr


def test_zsh_completion_with_insecure_inherited_fpath(
    monkeypatch, completion_files, tmp_path
):
    # CI runners can inherit completion directories that trigger compinit's prompt.
    insecure = tmp_path / "insecure-completions"
    insecure.mkdir(mode=0o777)
    insecure.chmod(0o777)
    defaults = run_shell("zsh", "print -r -- ${(j.:.)fpath}", tmp_path).stdout.strip()
    monkeypatch.setenv("FPATH", f"{insecure}:{defaults}")

    test_zsh_interactive_completion(
        "voicer --voice ma", "voicer --voice marin ", False, completion_files, tmp_path
    )


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("voicer --output", {"--output", "--output-dir"}),
        ("voicer --voice ma", {"marin"}),
        ("voicer -v alloy,ma", {"alloy,marin"}),
        ("voicer --voice=alloy,ma", {"--voice=alloy,marin"}),
        ("voicer --voice ", set(VOICE_CHOICES)),
        ("voicer --voice echo --voice ce", {"cedar"}),
        ("voicer --format=wa", {"--format=wav"}),
        ("voicer --format ", set(RESPONSE_FORMATS)),
        ("voicer -m tts", {"tts-1", "tts-1-hd"}),
        ("voicer --completion ", set(SHELLS)),
        ("voicer --file input", {"input with spaces.txt"}),
        ("voicer -o input", {"input with spaces.txt"}),
        ("voicer --output-dir audio", {"audio with spaces/"}),
        ("voicer --output-dir input", set()),
        ("voicer --speed ", set()),
        ("voicer --instructions --out", set()),
        ("voicer -- --out", set()),
    ],
)
def test_fish_completions(line, expected, completion_files, tmp_path):
    command = (
        f"source {shlex.quote(str(completion_files['fish']))}; "
        f"complete -C {shlex.quote(line)}"
    )
    result = run_shell("fish", command, tmp_path)

    assert {item.split("\t")[0] for item in result.stdout.splitlines()} == expected
    assert not result.stderr
