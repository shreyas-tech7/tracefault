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
