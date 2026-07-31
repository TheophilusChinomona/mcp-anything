---
description: "Check the live Speccon Dev PM MCP deployment: endpoint reachability, server name, tool count, methods, and rollback profile state."
---

# /devpm-status — DevPM deployment health check

Verifies the live Speccon Dev PM MCP server and reports deployment state. Does not call any business/write tool.

## What it checks

1. MCP handshake: `initialize` → session → `notifications/initialized` → `tools/list` against `http://100.102.160.49:8000/mcp`
2. Server name == `speccon-crm-devpm-write`
3. Tool count == 161 (139 reads + 22 writes)
4. No `delete_*` tool names; methods ⊆ {GET, POST, PUT, PATCH}
5. Rollback profile present: `output/speccon/profiles/devpm-read/generation_manifest.json` (139 tools)
6. Hub process: `speccon-devpm-http` running and ready

## Output

A compact table:

| Check | Expected | Actual | Status |
|---|---|---|---|
| Server name | speccon-crm-devpm-write | ... | ✅/❌ |
| Tool count | 161 | ... | ✅/❌ |
| DELETE tools | 0 | ... | ✅/❌ |
| Hub process | ready | ... | ✅/❌ |
| Read profile | present | ... | ✅/❌ |

Report any mismatch and the corrective step (see the speccon-devpm skill or AGENTS.md). Never call a write tool during this check.
