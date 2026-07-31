# CLAUDE.md

Operating guide for Claude Code (and compatible agents) in this repo.

## Read first

**`AGENTS.md`** is the authoritative operating guide: the live Speccon Dev PM deployment, ticket workflow rules, profile regeneration, deploy/rollback, and verification. Load it before any DevPM work.

## Live DevPM MCP

- Endpoint: `http://100.102.160.49:8000/mcp` — client alias `speccon-erp`
- Server: `speccon-crm-devpm-write` (161 tools, GET/POST/PUT/PATCH, no DELETE)
- Add via: `claude mcp add --transport http speccon-erp http://100.102.160.49:8000/mcp`
- Full agent behavioral spec: `docs/agent-prompts/speccon-erp-mcp-setup.md`
- Operator quick reference: the `speccon-devpm` skill

## Commands

- `/devpm-status` — deployment health check (server, tool count, methods, process)
- `/devpm-create-ticket` — guided DevPM ticket creation + assignment

## Project layout

| Path | Purpose |
|---|---|
| `mcp_anything/` | Generator, analyzer, runtime, LLM backends |
| `mcp_anything/runtime.py` | Runtime copied into every generated artifact as `mcp_runtime.py` |
| `ops/generate_devpm_profile.py` | Read/write DevPM profile generator (policy constants at top) |
| `specs/speccon-openapi.json` | **Private** — never commit, copy, or paste its contents |
| `output/speccon/profiles/` | Generated artifacts (gitignored) |
| `docs/agent-prompts/` | Agent setup prompts |
| `docs/superpowers/` | Design specs, implementation plans, deployment runbook |

## Guardrails

- Never put Speccon credentials in prompts, MCP config, tool args, logs, or commits — they live only in `/home/theo-zo/.config/mcp-anything/speccon-devpm.env` (mode 0600).
- Never call DELETE operations or non-ticket writes (policy denies them server-side; don't try to bypass).
- Runtime changes must be re-copied into every generated artifact (`mcp_runtime.py`) — regeneration alone only updates the profile you regenerate.
- Verify with `venv/bin/python -m pytest` before claiming work done.
- `main` is the live-tracking branch: commit feature work on feature branches, not `main`.
