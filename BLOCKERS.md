# Blockers

## Third-party skill install (2026-11-21)

- Step: `npx -y skills add DietrichGebert/ponytail -g -a claude-code -y`
- Error: "Permission for this action was denied by the Claude Code auto mode classifier."
- Instead: no retry and no other route, as the rules say. The ponytail rules (small, plain code, no new dependency), caveman (terse progress notes) and humanizer (plain docs) were applied by hand. superpowers skills were already in the session.
- Manual step: none needed for the repo. Shreyas can install the skills on his own machine.

## OTel GenAI repo commit SHA (2026-11-21)

- Step: `curl https://api.github.com/repos/open-telemetry/semantic-conventions-genai/commits/main`
- Error: "GitHub access to this repository is not enabled for this session."
- Instead: the raw docs fetched fine (HTTP 200). The pin is the fetch date plus sha256 of both files, in DECISIONS.md and model.py.

## Embedding clustering (2026-11-21)

- Step: FastEmbed needs its model from huggingface.co.
- Error: `curl https://huggingface.co` answers 000 (proxy refused).
- Instead: the brief's fallback. Signature clustering ships alone and the README says so. The idea is in docs/PROPOSALS.md.

## Provider hosts (2026-11-21)

- api.groq.com, openrouter.ai, api.osv.dev and semgrep.dev answer 000. No record mode is needed for this project. pip-audit and ruff S rules stand in for osv-scanner and semgrep.

## Bug triage log

- Live bug, fixed: `context_overflow` crashed (zip strict) on a trace with no model calls. Found by the ANSI escape test. Score 3 x 4 = 12, fixed at once.
- Live bug, fixed: three detectors crashed on odd attribute types (`finish_reasons` as a number, a tool definition whose name is a list, a required handoff field that is a list). Found in the release self review. Score 3 x 4 = 12, fixed at once with `test_odd_attribute_values_never_crash`.
- Live bugs, fixed after the outside review: huge JSON integers, numbers too large for a float, non-finite times, malformed OTLP shapes (`scopeSpans` or `status` of the wrong type) and spans that end before they start crashed with a traceback (exit 1, which CI reads as findings) or slipped through. They now raise `InputError` and exit 2. A span that names itself as parent is a root. A handoff payload sent as a JSON object is read instead of flagged. The bench now also refuses the seed in `thresholds.json`. HTML escapes control bytes. Each fix has a test.
