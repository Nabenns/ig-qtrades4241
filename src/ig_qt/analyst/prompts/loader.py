"""Prompt template loader."""
from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


class PromptTemplate:
    """A parsed prompt with `system` and `user` sections."""

    def __init__(self, *, version: str, system: str, user: str) -> None:
        self.version = version
        self.system = system
        self.user_template = user

    def render_user(self, **kwargs: object) -> str:
        return self.user_template.format(**kwargs)


def _split_sections(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[name] = text[start:end].strip()
    return parts


def load_prompt(name: str) -> PromptTemplate:
    """Load `<name>.md` from prompts/ directory by package resource."""
    pkg = "ig_qt.analyst.prompts"
    res = resources.files(pkg).joinpath(f"{name}.md")
    raw = Path(str(res)).read_text(encoding="utf-8")
    sections = _split_sections(raw)
    if "system" not in sections or "user template" not in sections:
        raise ValueError(f"prompt {name} missing required sections")
    return PromptTemplate(
        version=name, system=sections["system"], user=sections["user template"]
    )
