# MCP-Anything

**Generate MCP servers for OpenAPI APIs, with optional LLM enhancement.**

MCP-Anything converts an OpenAPI 3.x document into a runnable [FastMCP](https://github.com/modelcontextprotocol/python-sdk) server. The generated server exposes API operations as typed MCP tools and can be connected to Claude Desktop, Cursor, OpenClaw, or another MCP client.

## Current status

- **Tier 1 (OpenAPI generation):** supported and tested.
- **Tier 2 (website/API documentation discovery):** supported through Firecrawl.
- **LLM enhancement:** optional OpenAI, Anthropic, Google, OpenRouter, Claude SDK, and OpenAI Agents SDK integrations.
- **Tier 3 browser-interaction servers:** not implemented.
- **Remote Dev PM profile:** the repository contains a read-only SSH-over-Tailscale deployment runbook; remote provisioning requires an approved host, account, ACL, SSH key, and credentials.

## How it works

```text
OpenAPI JSON/YAML or URL
          │
          ▼
OpenAPIAnalyzer
  resolve refs, parameters, schemas, security, endpoints
          │
          ▼
MCPServerGenerator
  filter operations, generate typed FastMCP tools and runtime
          │
          ▼
Generated profile directory
  server.py + mcp_runtime.py + mcp_config.json + inventory + manifest + docs
          │
          ▼
MCP client over local stdio or SSH-backed stdio
```

The generated server uses the copied `mcp_runtime.py` for:

- API authentication with email/password login, refresh-token handling, or a static API token.
- JSON, form-encoded, and bounded multipart requests.
- Runtime capability checks for writes, tags, operation IDs, and HTTP methods.
- In-memory credentials and token state; credentials are not written into generated artifacts.

## Install

Requirements:

- Python 3.10 or newer.
- An OpenAPI 3.x JSON or YAML document, or a URL serving one.
- API credentials for the target service when the generated tools require authentication.

Install into an isolated virtual environment:

```bash
git clone https://github.com/TheophilusChinomona/mcp-anything.git
cd mcp-anything

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Optional dependency sets:

```bash
# Development and test dependencies
python -m pip install -e ".[dev]"

# All optional LLM and Agents SDK providers
python -m pip install -e ".[all]"

# Individual integrations
python -m pip install -e ".[openai]"
python -m pip install -e ".[anthropic]"
python -m pip install -e ".[google]"
python -m pip install -e ".[agents]"
```

Confirm the CLI is available:

```bash
mcp-anything llm-providers
```

## Generate an MCP server

Generate from a local or remote OpenAPI document:

```bash
mcp-anything generate \
  https://petstore3.swagger.io/api/v3/openapi.json \
  --output ./output/petstore

# Local JSON or YAML
mcp-anything generate ./specs/petstore.yaml --output ./output/petstore

# Inspect a specification without generating files
mcp-anything info ./specs/petstore.yaml
```

Useful generation controls:

```bash
# Name the server and its environment-variable prefix
mcp-anything generate spec.json \
  --output ./output/my-api \
  --name my-api \
  --env-prefix MY_API

# Keep only operations carrying selected OpenAPI tags
mcp-anything generate spec.json \
  --output ./output/read-profile \
  --tags Projects,Reports

# Keep only selected operation IDs
mcp-anything generate spec.json \
  --output ./output/small-profile \
  --operations listProjects,getProject

# Exclude selected operation IDs
mcp-anything generate spec.json \
  --output ./output/small-profile \
  --deny-operations deleteProject
```

Generated servers are read-only by default. `--allow-writes` is an explicit opt-in that includes state-changing operations; do not use it for an unreviewed or production profile.

To discover API documentation from a website:

```bash
export FIRECRAWL_API_KEY="..."
mcp-anything discover https://api.example.com --output ./output/discovery
```

## Generated artifacts

Every generated output directory contains the following files:

| File | Purpose |
|---|---|
| `{name}_server.py` | FastMCP server with one generated tool per selected endpoint |
| `mcp_runtime.py` | Self-contained authentication, HTTP, upload, and capability-policy runtime |
| `mcp_config.json` | MCP client configuration template |
| `tools_inventory.json` | Machine-readable registry of names, methods, paths, tags, parameters, and request bodies |
| `generation_manifest.json` | Generator identity, source hash, endpoint counts, profile name, and policy metadata |
| `.env.example` | Non-secret environment-variable template |
| `README.md` | Generated endpoint documentation and usage notes |
| `SKILL.md` | Agent-facing instructions for the generated tool set |

Keep `generation_manifest.json` with the generated artifact. It records the source SHA-256 so a deployed profile can be compared with the trusted workstation output.

## Configure and run a generated server

The environment prefix is derived from the server name unless `--env-prefix` is supplied. For a server named `my-api`, the generated variables are normally `MY_API_*`.

Set the generated values in the process environment. `.env.example` is a template; the generated server does not require or automatically load a `.env` file:

```bash
export MY_API_BASE_URL="https://api.example.com"
export MY_API_EMAIL="service-account@example.com"
export MY_API_PASSWORD="use-a-secret-manager-or-secure-shell"
export MY_API_API_KEY=""  # Use this instead of email/password when supported
export MY_API_ALLOW_WRITES="false"

python ./output/my-api/my_api_server.py
```

Use either email/password or a static API token as supported by the target API. Keep secrets outside Git, prompts, generated JSON, and `mcp_config.json`.

For a client configuration, start with the generated `mcp_config.json` and replace its command with the virtual-environment interpreter when needed:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/absolute/path/to/mcp-anything/.venv/bin/python",
      "args": [
        "/absolute/path/to/output/my-api/my_api_server.py"
      ],
      "env": {
        "MY_API_BASE_URL": "https://api.example.com",
        "MY_API_ALLOW_WRITES": "false",
        "MY_API_ALLOWED_METHODS": "GET"
      }
    }
  }
}
```

Do not put `MY_API_EMAIL`, `MY_API_PASSWORD`, or `MY_API_API_KEY` in shared client configuration when the client or filesystem is not a trusted secret store. Prefer a wrapper that sources a mode-640 environment file or the client’s approved secret mechanism.

## Agent setup instructions

These instructions are intended for an agent configuring an MCP client after a profile has been generated.

### 1. Inspect the profile before connecting it

```bash
cat output/my-api/generation_manifest.json
python -m json.tool output/my-api/tools_inventory.json >/dev/null
sed -n '1,160p' output/my-api/SKILL.md
```

Check:

1. `server_name`, `endpoint_count`, `spec_sha256`, and `allow_writes`.
2. The inventory’s `method`, `path`, `operation_id`, and `tags` for every tool you intend to use.
3. Whether the profile contains write methods. Treat any profile with `allow_writes: true` as requiring explicit human approval.

### 2. Register the server

Add the generated `mcp_config.json` entry to the selected MCP client, using absolute paths:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/absolute/path/to/mcp-anything/.venv/bin/python",
      "args": [
        "/absolute/path/to/output/my-api/my_api_server.py"
      ]
    }
  }
}
```

Restart the MCP client completely. Confirm that initialization succeeds and that the number of exposed tools matches the reviewed manifest/inventory.

### 3. Use the least-capable tool that satisfies the request

- Prefer `GET` tools for read-only work.
- Match the tool’s required parameters to `tools_inventory.json` before calling it.
- Do not infer that a similarly named operation is safe; inspect its HTTP method and path.
- Do not call `POST`, `PUT`, `PATCH`, or `DELETE` tools unless writes were explicitly approved for that profile.
- Never put credentials into a tool argument, prompt, generated file, or chat transcript.
- Report authentication, policy-denied, timeout, and HTTP errors without echoing secrets.

### 4. Verify without mutating data

For a new profile, first initialize the MCP connection and list tools. Then use one known harmless read operation. Do not use production-mutating calls as a connectivity test.

## Remote Dev PM profile over SSH and Tailscale

The repository’s current remote design uses SSH-backed MCP stdio, not a public HTTP listener:

```text
local MCP client
      │ launches
      ▼
ssh -T speccon-mcp /usr/local/bin/speccon-devpm-mcp
      │ over Tailscale
      ▼
remote wrapper → read-only Dev PM FastMCP server
```

The remote host must be provisioned by an operator. The private OpenAPI spec stays on the trusted workstation; only the generated profile directory and manifest are transferred.

### Generate the read-only profile locally

Run from the trusted workstation after obtaining the private spec through the approved process:

```bash
source .venv/bin/activate
python ops/generate_devpm_profile.py \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-read
```

The helper fixes these deployment properties:

- Server: `speccon-crm-devpm-read`
- Environment prefix: `SPECCON_DEVPM`
- Base URL: `https://prod-erp-backend.azurewebsites.net`
- Allowed methods: `GET` only
- Writes: disabled
- Dev PM tag allowlist: defined in `ops/generate_devpm_profile.py`

Review `generation_manifest.json` and record the repository commit and `spec_sha256`. Package only the generated profile:

```bash
tar --sort=name --owner=0 --group=0 --numeric-owner \
  -czf /tmp/speccon-devpm-read.tar.gz \
  -C output/speccon/profiles devpm-read

scp /tmp/speccon-devpm-read.tar.gz speccon-mcp:/tmp/
```

Do not transfer `specs/speccon-openapi.json`, the generator source, or credentials.

### Remote environment and wrapper

The remote secret file is `/etc/mcp-anything/speccon-devpm.env` and must include this non-secret policy structure:

```dotenv
SPECCON_DEVPM_BASE_URL=https://prod-erp-backend.azurewebsites.net
SPECCON_DEVPM_EMAIL=
SPECCON_DEVPM_PASSWORD=
SPECCON_DEVPM_API_KEY=
SPECCON_DEVPM_ALLOW_WRITES=false
SPECCON_DEVPM_ALLOWED_METHODS=GET
SPECCON_DEVPM_ALLOWED_TAGS=DevPmActivity,DevPmAudit,DevPmBugClaim,DevPmBugTriage,DevPmDashboard,DevPmDocumentImports,DevPmEpics,DevPmEvents,DevPmLabels,DevPmLearners,DevPmMetrics,DevPmNotifications,DevPmPhases,DevPmPoker,DevPmProjectPhases,DevPmProjects,DevPmQuestions,DevPmReleaseNotes,DevPmReports,DevPmSettings,DevPmSprints,DevPmSquads,DevPmSubFeatures,DevPmTeam,DevPmTicketSubtasks,DevPmTickets,DevPmUserPreferences
SPECCON_DEVPM_ALLOWED_OPERATIONS=
SPECCON_DEVPM_DENIED_OPERATIONS=
```

Fill credentials only from the approved remote secret store. Restrict the file to root and the dedicated `mcp-speccon` group:

```bash
sudo chown root:mcp-speccon /etc/mcp-anything/speccon-devpm.env
sudo chmod 0640 /etc/mcp-anything/speccon-devpm.env
```

The wrapper must preserve MCP stdout:

```bash
#!/usr/bin/env bash
set -euo pipefail
set -a
source /etc/mcp-anything/speccon-devpm.env
set +a

exec /opt/mcp-anything/venv/bin/python \
  /opt/mcp-anything/output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py
```

Do not print banners, credentials, or diagnostics to stdout. MCP protocol traffic owns stdout.

### Agent/client configuration for the remote profile

```json
{
  "mcpServers": {
    "speccon-remote": {
      "command": "ssh",
      "args": [
        "-T",
        "speccon-mcp",
        "/usr/local/bin/speccon-devpm-mcp"
      ]
    }
  }
}
```

Credentials belong only in the remote environment file, never in this JSON. After restarting the client, verify initialization and the reviewed tool count. For the current Dev PM profile, the expected result is **139 GET-only tools**.

The first deployment does not use Tailscale Funnel, public DNS, or Streamable HTTP. Tailscale Serve is a later option only if multiple clients require a shared URL.

### Ticket write profile

A write-capable profile (`speccon-crm-devpm-write`) is available alongside the read-only profile. It adds ticket and subtask workflow operations:

- Server: `speccon-crm-devpm-write`
- Environment prefix: `SPECCON_DEVPM` (same as read profile)
- Allowed methods: `GET, POST, PUT, PATCH`
- Writes: enabled (ticket-scoped only)
- Expected tools: 161 (139 reads + 22 ticket/subtask writes)
- Deletes: excluded (6 tools denied)

Generate:

```bash
python ops/generate_devpm_profile.py \
  --profile write \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-write
```

The agent prompt at `docs/agent-prompts/speccon-erp-mcp-setup.md` contains the behavioral rules for using the write profile.

## LLM enhancement

LLM enhancement is optional. It enriches descriptions and examples; it does not replace the OpenAPI schema or runtime capability policy.

| Provider | Default model | Environment variable |
|---|---|---|
| `hermes` | Built-in/local | None |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| `google` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| `openrouter` | `anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |

Examples:

```bash
mcp-anything generate spec.json --llm openai
mcp-anything generate spec.json --llm anthropic --llm-model claude-sonnet-4-20250514
mcp-anything generate spec.json --llm google
mcp-anything generate spec.json --llm openrouter \
  --llm-model meta-llama/llama-4-maverick

# Claude SDK native tool-use enhancement
mcp-anything generate spec.json --claude

# OpenAI Agents SDK pipeline
mcp-anything generate spec.json --agents
```

LLM keys are used during generation. They are separate from the generated API server’s credentials.

## Programmatic usage

```python
from mcp_anything import MCPServerGenerator, OpenAPIAnalyzer

analyzer = OpenAPIAnalyzer("https://api.example.com/openapi.json").load()
generator = MCPServerGenerator(
    analyzer,
    server_name="my-api",
    env_prefix="MY_API",
    allow_writes=False,
)
result = generator.generate("./output/my-api")
print(result["server_file"])
print(result["tool_count"])
```

For a reusable profile with explicit policy boundaries, pass `allowed_tags`, `allowed_operations`, `denied_operations`, and `allowed_methods` to `MCPServerGenerator`. The Dev PM helper is the reference implementation for a fixed, strict read-only profile.

## Development and tests

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

pytest
```

Generated artifacts should be smoke-tested by compiling the generated server beside its copied runtime and by checking `tools_inventory.json` against `generation_manifest.json`.

## Limitations and roadmap

- Browser-interaction MCP servers for arbitrary sites are not implemented.
- Streaming support is not implemented.
- OAuth2 and service-specific authentication helpers are not generalized; generated runtime support currently covers login/password and static token patterns.
- Rate limiting and retry policy beyond authentication refresh are not generalized.
- Remote Tailscale/SSH deployment remains an operator runbook, not an automated installer.
- Streamable HTTP/Tailscale Serve is deferred until multi-client access requires it.

## Relationship to CLI-Anything

| | CLI-Anything | MCP-Anything |
|---|---|---|
| **Output** | Click CLI commands | FastMCP tools |
| **Target** | Desktop software | APIs and web services |
| **Protocol** | Shell/terminal | Model Context Protocol |
| **Integration** | Claude Code, OpenClaw | Claude Desktop, Cursor, OpenClaw, or any MCP client |

## License

MIT
