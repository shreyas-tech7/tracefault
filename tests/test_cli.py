"""Exit codes: 0 no findings, 1 findings, 2 usage or input error. README documents them."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from builders import clean

from tracefault.cli import ERROR, FOUND, OK, main
from tracefault.convert import to_jsonl

EX = Path(__file__).resolve().parents[1] / "examples"


def _write(tmp_path, traces, name="t.jsonl"):
    p = tmp_path / name
    p.write_text(to_jsonl(traces))
    return str(p)


def test_exit_0_on_clean_traces(tmp_path, capsys):
    assert main(["scan", _write(tmp_path, [clean()])]) == OK
    assert "0 with findings" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["otel_genai.json", "simple.jsonl"])
def test_exit_1_on_findings(name, tmp_path, capsys):
    """Broken case: a scan that finds a failure but exits 0, so CI stays green."""
    html, js = tmp_path / "r.html", tmp_path / "r.json"
    assert main(["scan", str(EX / name), "--html", str(html), "--json", str(js)]) == FOUND
    out = capsys.readouterr().out
    assert "FAIL tool_error_loop" in out
    assert html.read_text().startswith("<!doctype html>")
    assert json.loads(js.read_text())["findings"][0]["type"] == "tool_error_loop"


def test_fail_on_limits_the_types(capsys):
    assert main(["scan", str(EX / "simple.jsonl"), "--fail-on", "timeout"]) == OK
    assert main(["scan", str(EX / "simple.jsonl"), "--fail-on", "timeout,tool_error_loop"]) == FOUND


@pytest.mark.parametrize(
    "args",
    [
        ["scan", "does-not-exist.jsonl"],
        ["scan", str(EX / "simple.jsonl"), "--fail-on", "nonsense"],
        ["scan", str(EX / "simple.jsonl"), "--format", "otlp"],
        ["scan", str(EX / "simple.jsonl"), "--prices", "missing.json"],
    ],
)
def test_exit_2_on_input_errors(args, capsys):
    assert main(args) == ERROR
    assert "tracefault: error:" in capsys.readouterr().err


def test_exit_2_on_bad_json_and_empty_input(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{oops\n")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert main(["scan", str(bad)]) == ERROR
    assert main(["scan", str(empty)]) == ERROR


def test_exit_2_on_usage_error():
    with pytest.raises(SystemExit) as e:
        main(["scan"])
    assert e.value.code == 2


def test_terminal_output_shows_control_characters_as_escapes(tmp_path, capsys):
    """Broken case: an ANSI escape in a trace rewrites the user's terminal."""
    line = {
        "trace_id": "a",
        "span_id": "r",
        "start": 0,
        "end": 1,
        "kind": "agent",
        "attrs": {"gen_ai.tool.definitions": []},
    }
    tool = {
        "trace_id": "a",
        "span_id": "s",
        "parent_id": "r",
        "start": 0,
        "end": 1,
        "kind": "tool",
        "tool": "evil\x1b[2J",
        "error": "x",
    }
    p = tmp_path / "e.jsonl"
    p.write_text(json.dumps(line) + "\n" + json.dumps(tool) + "\n")
    assert main(["scan", str(p)]) == FOUND
    out = capsys.readouterr().out
    assert "\x1b" not in out and "\\x1b[2J" in out


def test_console_script_exit_code(tmp_path):
    """The installed `tracefault` command returns the same code to the shell."""
    exe = Path(sys.executable).with_name("tracefault")
    r = subprocess.run(
        [str(exe), "scan", str(EX / "simple.jsonl"), "-q"],  # noqa: S603
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 1, r.stderr


def test_generate_and_demo(tmp_path):
    assert main(["generate", "--out", str(tmp_path / "g"), "--per-fault", "1", "--clean", "2"]) == OK
    truth = json.loads((tmp_path / "g" / "truth.json").read_text())["truth"]
    assert len(truth) == 10
    assert main(["scan", str(tmp_path / "g" / "traces.otlp.json"), "-q"]) == FOUND
    assert main(["demo", "--out", str(tmp_path / "d")]) == OK
    assert (tmp_path / "d" / "report.html").is_file()
