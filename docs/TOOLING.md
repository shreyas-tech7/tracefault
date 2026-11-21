# Tooling

| Tool | Source | Version | Why | Check result |
| --- | --- | --- | --- | --- |
| superpowers skills | already in the session (claude.ai account) | as installed | plans, TDD, debugging, verification, review | followed inline |
| ponytail, caveman, humanizer, find-skills | `npx skills add ...` | none | code style, terse progress, doc pass, skill search | not installed. The permission system denied the first `npx skills add` on 2026-11-21. No retry. Rules applied by hand |
| gitleaks | `go install github.com/zricethezav/gitleaks/v8@latest` | v8.30.1 | secret scan before each commit and on full history | installed |
| actionlint | `go install github.com/rhysd/actionlint/cmd/actionlint@latest` | v1.7.12 | workflow lint | installed |
| pip-audit | `uv tool install pip-audit` | see docs/RELEASE_CHECK.md | dependency audit | installed |
| ruff | PyPI (dev extra) | at install time | lint, format, `--select S` | runs in init.sh |
| graphify, cisco-ai-skill-scanner, pre-commit | `uv tool install` | not installed | not needed: under 30 source files, no third-party skills installed, gitleaks runs directly | skipped |
| security-audit | session skill | not used | the brief says skip it: no sign-in, personal data or payments | skipped by design |

## Repos from the shared list (GITHUB_REPOS.md)

| Repo | Fit | What happened |
| --- | --- | --- |
| obra/superpowers | yes | already in the session, used inline |
| DietrichGebert/ponytail, JuliusBrussee/caveman, blader/humanizer | yes | install denied by the permission system, rules followed by hand |
| gitleaks/gitleaks | yes | used |
| google/osv-scanner, semgrep/semgrep | partly | api.osv.dev and semgrep.dev did not answer. pip-audit and ruff S rules instead |
| Graphify-Labs/graphify | no | small codebase |
| meta-llama/PurpleLlama, protectai deberta model | no | the brief keeps LLM judges out of scope, and huggingface.co is blocked |
| cisco-ai-defense/skill-scanner, mcp-scanner | no | no skills or MCP server installed |
| NVIDIA/garak | no | needs a model endpoint |
| OmniRoute, litellm, free-llm-api-resources | no | no record mode in this brief |
| microsoft/playwright-mcp | no | the report is static HTML. Tests check the markup directly |
| unclecode/crawl4ai, wheresryan22/anatomy | no | no crawling. The figure is a stretch item |
| coreyhaines31/marketingskills | partly | README structure follows the brief. Not installed |
| NousResearch/hermes-agent | idea only | a real agent whose traces could feed tracefault. Listed in docs/PROPOSALS.md |
