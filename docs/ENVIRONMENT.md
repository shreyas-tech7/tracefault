# Environment

Probed on 2026-11-21 with `curl -sS -o /dev/null -w '%{http_code}' -m 10 <url>`.

| Host | Answer | Used for |
| --- | --- | --- |
| https://pypi.org/pypi/tracefault/json | 404 (reachable, name free) | Name check |
| https://registry.npmjs.org/tracefault | 404 (reachable, name free) | Name check |
| raw.githubusercontent.com, semantic-conventions-genai gen-ai-spans.md and gen-ai-agent-spans.md | 200 | OTel field names |
| https://huggingface.co | 000 (proxy refused) | Embedding clustering. Not shipped |
| https://api.groq.com, https://openrouter.ai | 000 (proxy refused) | Not needed. No record mode in this brief |
| https://api.osv.dev, https://semgrep.dev | 000 (proxy refused) | Not used. pip-audit and ruff S rules instead |

Machine: Intel(R) Xeon(R) Processor @ 2.10GHz, 4 cores, Python 3.11.18 in `.venv` (VM Python 3.13.18), uv 0.11.32.
No provider key variables were set. Nothing in this project needs one.
