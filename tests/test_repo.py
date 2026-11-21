"""Repo quality bar: README parts in order, generated numbers in sync, writing rules, files."""

import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from tracefault.cli import main
from tracefault.detect import DETECTORS
from tracefault.readme import FINAL, SECOND, write

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"```.*?```", re.S)
CODE = re.compile(r"`[^`]*`")
GEN = re.compile(r"<!-- gen:(\w+) -->.*?<!-- /gen:\1 -->", re.S)
SECTIONS = [
    "## The problem",
    "## How it works",
    "## Results",
    "## Cost per task",
    "## Run it in 10 minutes",
    "## Limits",
    "## Glossary",
    "## Related work",
    "## How this was built",
]


def test_readme_parts_in_order():
    text = (ROOT / "README.md").read_text()
    status = text.index("**Status:**")
    pos = [text.index(s) for s in SECTIONS]
    assert status < pos[0] and pos == sorted(pos)
    assert "```mermaid" in text and "badge.svg" in text
    assert "planted by a generator" in text and "Real traces can fail in other ways" in text
    assert "docs/build/BUILD_PROMPT.md" in text and "not done yet" in text


def test_generated_files_match_results():
    """Broken case: someone types a number into the README or the QA page by hand."""
    assert write(ROOT, check=True) == []
    res = json.loads((ROOT / FINAL).read_text())
    p = res["by_type"]["wrong_tool"]["recall"]
    line = f"{p['k']}/{p['n']} = {100 * p['rate']:.1f}%"
    assert line in (ROOT / "README.md").read_text()
    assert line in (ROOT / "docs" / "INTERVIEW_QA.md").read_text()


def test_no_percent_outside_generated_blocks():
    """Broken case: a result typed into the prose. Only the table header and glossary say 95%."""
    text = GEN.sub("", FENCE.sub("", (ROOT / "README.md").read_text()))
    found = set(re.findall(r"\d+(?:\.\d+)?%", text))
    assert found <= {"95%"}, found
    assert not re.search(r"\d+ percent", text)


def test_results_meet_the_brief():
    for name in (FINAL, SECOND):
        res = json.loads((ROOT / name).read_text())
        m = res["meta"]
        assert m["traces"] >= 1000 and m["seed"] != m["tune_seed"]
        assert set(res["by_type"]) == set(DETECTORS)
        for t in res["by_type"].values():
            for key in ("precision", "recall"):
                x = t[key]
                assert x["lo"] <= x["rate"] <= x["hi"]


def _prose(path: Path) -> str:
    return CODE.sub("", FENCE.sub("", path.read_text(encoding="utf-8")))


DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "docs" / "handoff" / "COWORK_PROMPT.md"] + [
    p for p in sorted((ROOT / "docs").glob("*.md")) if p.name not in {"DEMO.md"}
]


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_writing_rules(path):
    text = _prose(path)
    assert "—" not in text and "–" not in text, "no em or en dashes"
    assert " - " not in re.sub(r"\n\s*- ", "\n", text), "no dashes as punctuation"
    for line in text.splitlines():
        if not line.startswith("|"):
            assert ";" not in line, f"semicolon in prose: {line}"
    for bad in ("it is important to note", "testament", "pivotal", "seamless", "delve", "not just"):
        assert bad not in text.lower()


def test_ship_files():
    for f in [
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        ".env.example",
        ".pre-commit-config.yaml",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/feature_request.md",
        "docs/index.html",
        "docs/report-example.html",
        "docs/DEMO.md",
        "docs/topics.txt",
        "docs/GITHUB_ABOUT.md",
        "docs/WALKTHROUGH.md",
        "docs/INTERVIEW_QA.md",
        "docs/HUMAN_STEPS.md",
        "docs/handoff/COWORK_PROMPT.md",
        "docs/build/BUILD_PROMPT.md",
        "examples/otel_genai.json",
        "examples/simple.jsonl",
    ]:
        assert (ROOT / f).is_file(), f
    assert "Copyright (c) 2026 Shreyas" in (ROOT / "LICENSE").read_text()


def test_interview_qa_has_about_fifteen_questions():
    qs = re.findall(r"^\*\*\d+\. .+\?\*\*$", (ROOT / "docs" / "INTERVIEW_QA.md").read_text(), re.M)
    assert 12 <= len(qs) <= 20


def test_social_preview_size():
    head = (ROOT / "docs" / "social-preview.png").read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", head[16:24]) == (1280, 640)


def test_topics():
    topics = (ROOT / "docs" / "topics.txt").read_text().split()
    assert 5 <= len(topics) <= 20
    assert all(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,24}", t) for t in topics)


def test_exit_codes_documented():
    text = (ROOT / "README.md").read_text()
    for code in ("| 0 |", "| 1 |", "| 2 |"):
        assert code in text, code


def test_example_report_is_current(tmp_path):
    """Broken case: the report code changes and the shipped example page goes stale."""
    out = tmp_path / "r.html"
    code = main(
        [
            "scan",
            str(ROOT / "examples" / "demo-traces.jsonl"),
            "--html",
            str(out),
            "--title",
            "tracefault example report",
            "-q",
        ]
    )
    assert code == 1
    assert out.read_text() == (ROOT / "docs" / "report-example.html").read_text()


def test_link_check_passes():
    r = subprocess.run(  # noqa: S603 (fixed argv, our own script)
        [sys.executable, str(ROOT / "scripts" / "check_links.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout
