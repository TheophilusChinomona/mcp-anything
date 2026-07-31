# Speccon DevPM Agent Setup Prompt

Copy the block below into a fresh agent session (Claude Code, Oh My Pi, or any MCP-capable agent) to set up DevPM operations autonomously. It creates the project's agent documentation, skill, and commands, then registers the MCP server.

```text
You are setting up agentic access to the Speccon ERP Dev PM system in this repository. Work autonomously; only stop to ask if a decision below is genuinely ambiguous.

## Step 1 — Load the source material

Read these files first (they already exist):
- AGENTS.md — operating guide (deployment facts, ticket rules, regeneration, rollback, verification)
- CLAUDE.md — Claude Code operating guide
- docs/agent-prompts/speccon-erp-mcp-setup.md — the authoritative agent behavioral spec
- docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md — operator runbook

## Step 2 — Verify the live deployment (no writes)

1. Initialize an MCP session against http://100.102.160.49:8000/mcp (Streamable HTTP):
   - POST initialize with protocolVersion 2024-11-05, capture the mcp-session-id header
   - POST notifications/initialized with that session id
   - POST tools/list with the session id — a bare tools/list without a session returns 400 "Missing session ID"
2. Confirm: server name == speccon-crm-devpm-write, exactly 161 tools, no tool name starting with "delete_", methods only GET/POST/PUT/PATCH.
3. Confirm the rollback profile exists: output/speccon/profiles/devpm-read/generation_manifest.json with endpoint_count 139.
4. Confirm the omp hub process speccon-devpm-http is running and ready.
Report the verification table; do NOT call any write tool.

## Step 3 — Create or refresh agent docs (if missing or stale)

Ensure these files exist in the repo and match the live deployment (server speccon-crm-devpm-write, 161 tools, GET/POST/PUT/PATCH, no DELETE):
- AGENTS.md at repo root: deployment facts table, ticket workflow (routine vs confirmation-required writes), never-list (DELETE, non-ticket writes, credential exposure, policy circumvention, auto-retry), ticket creation + assignment gotcha (Create does not assign; assign via put_api_devpm_devpmtickets_update with assigneeUserId), profile regeneration commands, deploy/rollback summary, verification, credentials policy.
- CLAUDE.md at repo root: point at AGENTS.md, register speccon-erp via `claude mcp add --transport http speccon-erp http://100.102.160.49:8000/mcp`, list the project commands, project layout table, guardrails.
- .claude/commands/devpm-status.md and .claude/commands/devpm-create-ticket.md (create if missing; refresh server name/tool count if stale).
- ~/.claude/skills/speccon-devpm/SKILL.md — the operator skill. Frontmatter: name "speccon-devpm", description starting "Use when working with the Speccon ERP Dev PM MCP server — ...". Content: live facts, ticket create/assign flow, confirmation rules, regeneration, deploy/rollback, diagnosis (401 handling, tool-count mismatches, MCP handshake), verification, credentials.
If a file already exists and matches, leave it; do not rewrite working docs.

## Step 4 — Register the MCP server in this client

Add speccon-erp if not already present, without removing other servers:
- Claude Code: `claude mcp add --transport http speccon-erp http://100.102.160.49:8000/mcp`
- Otherwise: add {"mcpServers": {"speccon-erp": {"url": "http://100.102.160.49:8000/mcp"}}} to the client's config, preserving existing entries.
Reload/restart the client if needed, then re-verify initialization and 161 tools.

## Step 5 — Commit

Commit the created/updated docs (AGENTS.md, CLAUDE.md, .claude/) on a feature branch:
git add AGENTS.md CLAUDE.md .claude/ && git commit -m "docs: agent setup for Speccon DevPM"
Do not commit specs/speccon-openapi.json, output/, or any credential-bearing file.

## Rules you must follow

- Never expose or print SPECCON_DEVPM credentials; they live only in /home/theo-zo/.config/mcp-anything/speccon-devpm.env (mode 0600).
- Never call a DELETE operation or a non-ticket write.
- Never auto-retry a failed write; report auth vs policy vs backend errors distinctly.
- Never run a production write during this setup — verification is read-only.
- If a write endpoint 401s while GETs work, note it and (with approval) restart speccon-devpm-http once; the runtime now refreshes tokens on 401 for all methods.
- Confirm high-impact actions (assignment, approvals, batch updates) with the user before calling them.
```

## Operator notes

- Re-run this prompt after any deployment change (new tool count, method set, server name) to refresh the docs.
- The skill is installed at `~/.claude/skills/speccon-devpm/` (user-level) so it applies to any project session that touches Speccon; commands are repo-level in `.claude/commands/`.
- If your runtime uses a different skills path, move the SKILL.md accordingly and update Step 3.
