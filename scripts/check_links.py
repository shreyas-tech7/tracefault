"""Check every relative link and anchor in the Markdown and HTML files.

Fails on missing files, missing anchors, bare `#` links and placeholder text
(`<owner>`, `TODO`, `example.com`). External links are listed as not checked.
`docs/build/BUILD_PROMPT.md` is skipped: it is a word-for-word copy of the brief.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".venv",
    ".git",
    "node_modules",
    ".cache",
    "logs",
    "raw",
    "graphify-out",
    ".pytest_cache",
    ".ruff_cache",
}
SKIP_FILES = {ROOT / "docs" / "build" / "BUILD_PROMPT.md"}
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_LINK = re.compile(r'(?:href|src)="([^"]+)"')
PLACEHOLDER = re.compile(r"<owner>|\bTODO\b|example\.com")
FENCE = re.compile(r"```.*?```", re.S)


def slug(heading: str) -> str:
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    if path.suffix == ".md":
        text = FENCE.sub("", path.read_text(encoding="utf-8"))
        return {slug(m) for m in re.findall(r"^#{1,6}\s+(.*)$", text, re.M)}
    return set(re.findall(r'id="([^"]+)"', path.read_text(encoding="utf-8")))


def files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if p.suffix in (".md", ".html") and not SKIP_DIRS & set(p.relative_to(ROOT).parts):
            if p not in SKIP_FILES:
                out.append(p)
    return sorted(out)


def main() -> int:
    errors, external = [], set()
    for f in files():
        text = f.read_text(encoding="utf-8")
        body = FENCE.sub("", text) if f.suffix == ".md" else text
        for m in PLACEHOLDER.finditer(body):
            errors.append(f"{f.relative_to(ROOT)}: placeholder {m.group()!r}")
        links = MD_LINK.findall(body) if f.suffix == ".md" else HTML_LINK.findall(body)
        for link in links:
            if link.startswith(("http://", "https://")):
                external.add(link)
                continue
            if link.startswith(("mailto:", "data:")):
                continue
            if link == "#":
                errors.append(f"{f.relative_to(ROOT)}: bare # link")
                continue
            target, _, anchor = link.partition("#")
            dest = (f.parent / target).resolve() if target else f
            if not dest.exists():
                errors.append(f"{f.relative_to(ROOT)}: missing {link}")
            elif anchor and dest.is_file() and anchor not in anchors(dest):
                errors.append(f"{f.relative_to(ROOT)}: missing anchor {link}")
    for e in errors:
        print("FAIL", e)
    print(f"checked {len(files())} files, {len(errors)} problems, {len(external)} external links not checked")
    for link in sorted(external):
        print("  not checked:", link)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
