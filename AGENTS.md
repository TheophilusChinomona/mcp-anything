# AGENTS.md — MCP-Anything + Speccon DevPM

Operating guide for agentic workers in this repository. Read this before working with the DevPM MCP server, generating profiles, or touching deployment state.

## What this repo is

MCP-Anything generates FastMCP servers from OpenAPI specs. Its live production use is the **Speccon ERP Dev PM** MCP server, which runs from this repo's generated artifacts.

## The live DevPM deployment

| Item | Value |
|---|---|
| Endpoint | `http://100.102.160.49:8000/mcp` (Tailscale IP, port 8000) |
| Client alias | `speccon-erp` |
| Live server | `speccon-crm-devpm-write` — **161 tools** (139 reads + 22 ticket/subtask writes) |
| Methods | `GET, POST, PUT, PATCH` — **no DELETE** |
| Dormant | `speccon-crm-devpm-read` (139 tools, GET-only) — rollback profile |
| Env prefix | `SPECCON_DEVPM` |
| Base URL | `https://prod-erp-backend.azurewebsites.net` |
| Wrapper | `/home/theo-zo/.local/bin/speccon-devpm-http` |
| Env file | `/home/theo-zo/.config/mcp-anything/speccon-devpm.env` (mode 0600, outside Git) |
| Process | omp hub service `speccon-devpm-http` |
| Agent prompt | `docs/agent-prompts/speccon-erp-mcp-setup.md` |
| Runbook | `docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md` |

## Working with tickets (write profile)

The MCP server enforces the policy server-side; the agent prompt at `docs/agent-prompts/speccon-erp-mcp-setup.md` is the authoritative behavioral spec. Summary:

**"My tickets" read flow** (no `/Me` endpoint yet — tracked as DevPM #499): `get_api_devpm_activity_getuserfeed` → `performedByUserId` = current user → `get_api_devpm_devpmtickets_getlist` with `assigneeuserid` (+ optional `status`). Do NOT use `getsubscribed` for this — subscribed = followed, not assigned. `DevPmTickets` family is canonical over legacy `Tickets`.

**Routine writes** (proceed after parameter validation): creating tickets, adding comments, creating subtasks, uploading attachments.

**Require explicit user confirmation before:** assignment/delegation/collaborator changes; approvals or rejections (QA reject, approve, park); review-flag changes; batch planning status updates; adding/removing links; creating/resolving questions; any ambiguous write.

**Never:**
- Call any `DELETE` operation (six are denied by policy).
- Write to projects, sprints, squads, settings, epics, labels, release notes, document imports, bug claims, or unrelated admin endpoints.
- Expose or print credentials; they live only in the server-side env file.
- Circumvent policy/auth errors, or auto-retry a failed write.

**Write flow:** read the tool description and HTTP method → verify operation ID → validate params → confirm high-impact actions → narrowest scope.

## Ticket creation

Create tickets through the MCP server with `post_api_devpm_devpmtickets_create`. Body uses `CreateDevPmSnagDto`: `title`, `description`, `acceptanceCriteria`, `technicalDetails`, `ticketType` (e.g. `Bug`), `projectKey` (UUID from `get_api_devpm_devpmprojects_getlist`).

**Assignment gotcha:** Create sets `reporterUserId` from the authenticated account but leaves `assigneeUserId` empty. Tickets are assigned via `put_api_devpm_devpmtickets_update` with `body.assigneeUserId` (int). An unassigned ticket does not appear on the board. Assigning is a confirmation-required write.

## Regenerating profiles

Both profiles are generated from the private spec (`specs/speccon-openapi.json`, never commit or copy it):

```bash
# read-only rollback profile (139 tools)
python ops/generate_devpm_profile.py --profile read \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-read

# live write profile (161 tools)
python ops/generate_devpm_profile.py --profile write \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-write
```

Generator policy constants (22 write ops, 6 denied deletes, method sets) live at the top of `ops/generate_devpm_profile.py`. The generator copies `mcp_anything/runtime.py` into each artifact as `mcp_runtime.py` — **any runtime change requires regenerating (or re-copying) every artifact**, including `academy-read`, `hr-write`, and `devpm-read`.

## Deploying / rollback (theo-zo host)

Deploy = regenerate → update env policy → repoint wrapper → restart `speccon-devpm-http` via the omp hub → verify. Full steps: `docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md`.

Rollback to read-only: archive write profile, restore `devpm-read`, set `SPECCON_DEVPM_ALLOW_WRITES=false` and `SPECCON_DEVPM_ALLOWED_METHODS=GET` in the env file, repoint wrapper, restart, verify 139 tools.

## Verification

- Test suite: `venv/bin/python -m pytest` — must be green before claiming work done.
- Live endpoint: initialize MCP session, `tools/list`, expect 161 tools, no `DELETE` method prefix.
- Never call a production write during automated verification; smoke writes need explicit operator approval.

## Credentials

Server-side credentials (`SPECCON_DEVPM_EMAIL/PASSWORD/API_KEY`) live only in `/home/theo-zo/.config/mcp-anything/speccon-devpm.env` (mode 0600). Never put them in prompts, client JSON, generated artifacts, logs, commits, or this repo.
