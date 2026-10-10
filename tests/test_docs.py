"""Documentation stays in sync with the CLI."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SKILL = ROOT / "skills" / "tgbot" / "SKILL.md"
REFERENCE = ROOT / "skills" / "tgbot" / "references" / "reference.md"

SUBGROUPS = {"chat", "bot", "key"}


def _command_paths(text: str) -> set[tuple[str, ...]]:
    """``tgbot <cmd> [<sub>]`` invocations found in the text (options excluded)."""
    paths: set[tuple[str, ...]] = set()
    for match in re.finditer(r"\btgbot((?:[ \t]+-{0,2}[a-z][a-z-]*)+)", text):
        words = [w for w in match.group(1).split() if not w.startswith("-")]
        if not words:
            continue
        path = tuple(words[:2]) if words[0] in SUBGROUPS and len(words) > 1 else (words[0],)
        paths.add(path)
    return paths


def _code(text: str) -> str:
    """Fenced code blocks plus inline `code` spans: the places commands are written."""
    blocks = re.findall(r"```(?:bash|console)?\n(.*?)```", text, flags=re.S)
    inline = re.findall(r"`(tgbot[^`\n]*)`", re.sub(r"```.*?```", "", text, flags=re.S))
    return "\n".join(blocks + inline)


def _ids(path: tuple[str, ...]) -> str:
    return " ".join(path)


@pytest.mark.parametrize("path", sorted(_command_paths(_code(README.read_text()))), ids=_ids)
def test_readme_commands_exist(cli, path):
    result = cli(*path, "--help")
    assert result.exit_code == 0, f"`tgbot {' '.join(path)}` from README: {result.stderr}"


def test_skill_frontmatter():
    text = SKILL.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    assert match, "SKILL.md must start with YAML frontmatter"
    frontmatter = match.group(1)
    assert re.search(r"^name: tgbot$", frontmatter, flags=re.M)
    assert re.search(r"^description: ", frontmatter, flags=re.M)


@pytest.mark.parametrize(
    "path",
    sorted(_command_paths(_code(SKILL.read_text()) + "\n" + _code(REFERENCE.read_text()))),
    ids=_ids,
)
def test_skill_commands_exist(cli, path):
    result = cli(*path, "--help")
    assert result.exit_code == 0, f"`tgbot {' '.join(path)}` from the skill: {result.stderr}"


def test_skill_mentions_every_send_command(cli):
    help_text = cli("--help").stdout
    commands = set(re.findall(r"^\s+(send[a-z]*)\s", help_text, flags=re.M))
    assert len(commands) == 13
    skill = SKILL.read_text()
    missing = {c for c in commands if f"`{c}" not in skill and f" {c} " not in skill}
    assert not missing
