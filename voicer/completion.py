"""Generate native shell completions from the CLI's argument definitions."""

import argparse
from pathlib import Path
from shlex import quote

from .config import DEFAULT_MODEL, VOICES

SHELLS = ("bash", "zsh", "fish")
KNOWN_MODELS = (DEFAULT_MODEL, "gpt-4o-mini-tts-2025-12-15", "tts-1", "tts-1-hd")
VOICE_CHOICES = (*VOICES, *(str(i) for i in range(1, len(VOICES) + 1)), "all")


def _choices(action: argparse.Action) -> tuple[str, ...]:
    if action.dest == "voice_selections":
        return VOICE_CHOICES
    if action.dest == "model":
        return KNOWN_MODELS
    return tuple(str(value) for value in action.choices or ())


def _description(action: argparse.Action) -> str:
    return (action.help or "").replace("%(default)s", str(action.default))


def generate_completion(parser: argparse.ArgumentParser, shell: str) -> str:
    """Return a script registering completion for the installed voicer command."""
    actions = [action for action in parser._actions if action.option_strings]
    match shell:
        case "bash":
            return _bash(actions)
        case "zsh":
            return _zsh(actions)
        case "fish":
            return _fish(actions)
        case _:
            raise ValueError(f"Unsupported shell: {shell}")


def _bash(actions: list[argparse.Action]) -> str:
    options = " ".join(option for action in actions for option in action.option_strings)
    value_options = "|".join(
        option
        for action in actions
        if action.nargs != 0
        for option in action.option_strings
    )
    cases = []
    for action in actions:
        if action.nargs == 0:
            continue
        pattern = "|".join(action.option_strings)
        choices = _choices(action)
        if action.dest == "voice_selections":
            body = f"choices={quote(' '.join(choices))}; list_value=1"
        elif choices:
            body = f"choices={quote(' '.join(choices))}"
        elif action.type is Path:
            kind = "-d" if action.dest == "output_dir" else "-f"
            body = f"path_kind={kind}"
        else:
            body = "return"
        cases.append(f"        {pattern}) {body} ;;")

    return (
        _BASH.replace("@OPTIONS@", quote(options))
        .replace("@VALUE_OPTIONS@", value_options)
        .replace("@CASES@", "\n".join(cases))
    )


_BASH = r"""# Bash completion for voicer. Source this file to activate it.
_voicer_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}" option='' prefix='' word candidate
    local choices='' path_kind='' list_value=0 end_options=0 i
    COMPREPLY=()

    # Track value-taking options, including Bash's separate '=' word.
    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        if [[ -n "$option" ]]; then
            [[ "$word" == '=' ]] || option=''
            continue
        fi
        [[ "$end_options" == 1 ]] && continue
        case "$word" in
            --) end_options=1 ;;
            @VALUE_OPTIONS@) option="$word" ;;
        esac
    done
    [[ "$end_options" == 1 ]] && return

    if [[ -n "$option" && "$cur" == '=' ]]; then
        cur=''
    elif [[ -z "$option" && "$cur" == --*=* ]]; then
        option="${cur%%=*}"
        prefix="$option="
        cur="${cur#*=}"
    fi

    if [[ -z "$option" ]]; then
        if [[ "$cur" == -* || -z "$cur" ]]; then
            while IFS= read -r candidate; do
                COMPREPLY+=("$candidate")
            done < <(compgen -W @OPTIONS@ -- "$cur")
        fi
        return
    fi

    case "$option" in
@CASES@
        *) return ;;
    esac
    if [[ -n "$path_kind" ]]; then
        while IFS= read -r candidate; do
            [[ -d "$candidate" ]] && candidate="$candidate/"
            COMPREPLY+=("$prefix$candidate")
        done < <(compgen "$path_kind" -- "$cur")
        # compopt is unavailable in macOS's Bash 3.2.
        if type compopt &>/dev/null; then
            compopt -o filenames 2>/dev/null || :
        fi
        return
    fi
    if [[ "$list_value" == 1 && "$cur" == *,* ]]; then
        prefix="$prefix${cur%,*},"
        cur="${cur##*,}"
    fi
    while IFS= read -r candidate; do
        COMPREPLY+=("$prefix$candidate")
    done < <(compgen -W "$choices" -- "$cur")
}
complete -o filenames -F _voicer_complete voicer
"""


def _zsh(actions: list[argparse.Action]) -> str:
    specs = []
    for action in actions:
        description = _description(action)
        for char in "\\[]:":
            description = description.replace(char, "\\" + char)
        repeat = isinstance(action, argparse._AppendAction)
        group = "" if repeat else f"({' '.join(action.option_strings)})"
        suffix = ""
        if action.nargs != 0:
            choices = _choices(action)
            if action.dest == "voice_selections":
                completion = "_voicer_voices"
            elif choices:
                completion = f"({' '.join(choices)})"
            elif action.type is Path:
                completion = "_files -/" if action.dest == "output_dir" else "_files"
            else:
                completion = ""
            suffix = f":{action.dest.replace('_', ' ')}:{completion}"
        for option in action.option_strings:
            attachment = ""
            if action.nargs != 0:
                attachment = "=" if option.startswith("--") else "+"
            spec = f"{'*' if repeat else ''}{group}{option}{attachment}[{description}]{suffix}"
            specs.append(quote(spec))

    arguments = " \\\n        ".join([*specs, quote("1:text:")])
    return f"""#compdef voicer
# Zsh completion for voicer. Load after compinit, or install as _voicer on fpath.
_voicer_voices() {{
    local -a voices
    voices=({" ".join(VOICE_CHOICES)})
    compset -P '*,'
    _describe -t voices 'voice' voices
}}
_voicer() {{
    _arguments -s -S \\
        {arguments}
}}
if [[ "$funcstack[1]" == _voicer ]]; then
    _voicer "$@"
else
    compdef _voicer voicer
fi
"""


def _fish(actions: list[argparse.Action]) -> str:
    lines = [
        "# Fish completion for voicer. Source or install as voicer.fish.",
        "complete -c voicer -f",
        "function _voicer_complete_voices",
        "    set -l token (commandline -ct)",
        "    set -l prefix ''",
        "    if string match -q -- '--*=*' \"$token\"",
        '        set token (string split -m 1 = -- "$token")[2]',
        "    end",
        "    if string match -q -- '*,*' \"$token\"",
        '        set -l parts (string split -r -m 1 , -- "$token")',
        '        set prefix "$parts[1],"',
        '        set token "$parts[2]"',
        "    end",
        f"    for voice in {' '.join(VOICE_CHOICES)}",
        '        if string match -q -- "$token*" "$voice"',
        "            printf '%s\\n' \"$prefix$voice\"",
        "        end",
        "    end",
        "end",
    ]
    for action in actions:
        parts = ["complete -c voicer"]
        for option in action.option_strings:
            kind = "-l" if option.startswith("--") else "-s"
            parts.extend([kind, option.lstrip("-")])
        parts.extend(["-d", quote(_description(action))])
        if action.nargs != 0:
            parts.append("-r")
            choices = _choices(action)
            if action.dest == "voice_selections":
                parts.extend(["-f -a", quote("(_voicer_complete_voices)")])
            elif choices:
                parts.extend(["-f -a", quote(" ".join(choices))])
            elif action.type is Path:
                if action.dest == "output_dir":
                    parts.extend(["-f -a", quote("(__fish_complete_directories)")])
                else:
                    parts.append("-F")
            else:
                parts.append("-f")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"
