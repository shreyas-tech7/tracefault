import json
from pathlib import Path

import pytest

from tracefault.bench import TUNE_SEED, run_bench, tune, wilson
from tracefault.detect import DEFAULTS, load_thresholds
from tracefault.generate import FAULTS, generate

ROOT = Path(__file__).resolve().parents[1]


def test_wilson_known_values():
    lo, hi = wilson(0, 100)
    assert lo == 0.0 and hi == pytest.approx(0.0370, abs=1e-3)
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)


def test_generator_is_deterministic_and_truth_stays_outside_the_traces():
    a, ta = generate(3, 3, seed=5)
    b, tb = generate(3, 3, seed=5)
    assert ta == tb and [t.trace_id for t in a] == [t.trace_id for t in b]
    assert sorted(v for v in ta.values() if v) == sorted(f for f in FAULTS for _ in range(3))
    names = [f for f in FAULTS if f != "timeout"]  # "timeout" is also real error text
    for t in a:
        for s in t.spans:
            blob = json.dumps(s.attrs) + s.name + (s.error or "")
            assert not any(f in blob for f in names), "ground truth leaked into a trace"
            assert not any(w in k for k in s.attrs for w in ("truth", "planted", "ground"))


def test_clean_traces_stay_inside_their_limits():
    traces, truth = generate(0, 200, seed=9)
    for t in traces:
        limit = t.conf("tracefault.context_limit")
        budget = t.conf("tracefault.budget_tokens")
        if limit:
            assert max(s.input_tokens for s in t.spans) <= 0.92 * limit
        if budget:
            assert sum(s.tokens for s in t.spans) < budget


def test_bench_refuses_the_tuning_seed():
    """Broken case: final numbers measured on the seed the thresholds were tuned on."""
    with pytest.raises(ValueError):
        run_bench(TUNE_SEED, DEFAULTS, 2, 2)


def test_small_bench_shape():
    r = run_bench(42, DEFAULTS, 5, 10)
    assert r["meta"]["traces"] == 50 and set(r["by_type"]) == set(FAULTS)
    for v in r["by_type"].values():
        assert v["precision"]["lo"] <= v["precision"]["rate"] <= v["precision"]["hi"]


def test_shipped_thresholds_come_from_tuning_seed():
    """The shipped thresholds equal a fresh tuning run on the tuning seed."""
    data = json.loads((ROOT / "src" / "tracefault" / "thresholds.json").read_text())
    assert data["tuned_on_seed"] == TUNE_SEED
    assert tune(TUNE_SEED)["thresholds"] == data["thresholds"] == load_thresholds()


def test_final_results_use_a_held_out_seed():
    res = json.loads((ROOT / "results" / "final-seed2026.json").read_text())
    assert res["meta"]["seed"] != res["meta"]["tune_seed"] == TUNE_SEED
    assert res["meta"]["traces"] >= 1000
    assert res["meta"]["thresholds"] == load_thresholds()
