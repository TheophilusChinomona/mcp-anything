# Remote Dev PM MCP Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the read-only Dev PM MCP profile on a Tailscale-connected host and let local agents access it through an SSH-backed stdio MCP connection without exposing an internet-facing service.

**Architecture:** The remote host runs the generated Dev PM read-only profile as a child process of each SSH MCP session. The local MCP client launches `ssh -T speccon-mcp ...`; SSH carries MCP stdin/stdout over the Tailscale network. Backend credentials remain in a restricted environment file readable only by root and `mcp-speccon`, and the first deployment exposes no write-capable profile and no HTTP listener. Streamable HTTP through Tailscale Serve is a later, optional phase for multi-client access.

**Tech Stack:** Python 3.12 virtual environment, existing generated FastMCP server, FastMCP stdio transport, OpenSSH over Tailscale, systemd-independent per-session wrapper, Claude Desktop or another stdio-capable MCP client.

## Global Constraints

- Deploy the generated Dev PM read-only profile first: `output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py`.
- Keep `SPECCON_DEVPM_ALLOW_WRITES=false` permanently for the first deployment.
- Do not expose the MCP process through Tailscale Funnel, public DNS, or a public firewall rule.
- Store `SPECCON_DEVPM_EMAIL`, `SPECCON_DEVPM_PASSWORD`, or `SPECCON_DEVPM_API_KEY` only on the remote host; never place them in Git, MCP JSON, shell history, or the plan.
- Use a dedicated Speccon service account with only the permissions needed by the Dev PM read profile.
- Do not call production-mutating endpoints during verification.
- Preserve MCP stdout for protocol traffic; diagnostics go to stderr or remote system logs.
- Pin the generated artifact to a known local repository commit and record the generated manifest SHA-256.
- Roll back by removing the local MCP entry and disabling the dedicated remote account/key; do not alter backend data or services.
- Keep the private OpenAPI spec on the trusted build workstation; transfer only the generated Dev PM profile artifact and its manifest to the remote host.

## Deployment Values

Use these fixed deployment paths and names so the client configuration, wrapper, and verification commands agree:

| Item | Value |
|---|---|
| Tailscale/SSH host alias | `speccon-mcp` |
| Remote Unix user | `mcp-speccon` |
| Remote artifact root | `/opt/mcp-anything/output/speccon` |
| Remote Python | `/opt/mcp-anything/venv/bin/python` |
| Remote secret file | `/etc/mcp-anything/speccon-devpm.env` |
| Remote MCP wrapper | `/usr/local/bin/speccon-devpm-mcp` |
| Generated server | `/opt/mcp-anything/output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py` |
| MCP profile | `speccon-crm-devpm-read` |
| Expected tool count | `139` |
| Expected methods | `GET` only |

---

### Task 1: Prepare the Tailscale-connected host

**Files:**
- Create: `ops/generate_devpm_profile.py`
- Create: `/etc/mcp-anything/speccon-devpm.env`
- Create: `/usr/local/bin/speccon-devpm-mcp`
- Modify: remote package and service-account state only; no private OpenAPI spec on the remote host

**Interfaces:**
- Produces the `speccon-mcp` SSH target and the remote executable `/usr/local/bin/speccon-devpm-mcp`.
- The wrapper must read the environment file, then `exec` the generated server so stdin/stdout remain connected to SSH.

- [ ] **Step 1: Install and authenticate Tailscale**

Install Tailscale on the remote Linux host, authenticate it to the intended tailnet, and verify the host has a stable tailnet hostname:

```bash
tailscale status
hostname -f
```

Do not enable Funnel. Restrict access with a Tailscale ACL that permits only the development workstation or approved agent devices to reach the host's SSH service.

- [ ] **Step 2: Create the dedicated Unix account**

Create `mcp-speccon` without administrative privileges and without access to unrelated application data:

```bash
sudo useradd --system --create-home --home-dir /home/mcp-speccon --shell /bin/bash mcp-speccon
sudo install -d -o root -g mcp-speccon -m 0750 /etc/mcp-anything
```

The account must be able to read the generated deployment artifact and secret file, but must not be able to modify system services, SSH configuration, or other users' files.

- [ ] **Step 3: Generate and transfer the pinned profile artifact**

Generate the profile on the trusted workstation, not on the remote host. The tracked helper must load the private spec from the workstation, set the fixed Speccon base URL, and call the reusable `MCPServerGenerator` with the Dev PM tag allowlist, `server_name="speccon-crm-devpm-read"`, `env_prefix="SPECCON_DEVPM"`, and `allow_writes=False`.

Run:

```bash
cd /home/theo-zo/dev/mcp-anything
source venv/bin/activate
python3 ops/generate_devpm_profile.py \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-read
```

The command must generate exactly 139 tools, a `tools_inventory.json`, `mcp_runtime.py`, the server module, and `generation_manifest.json`. Record the local repository commit and manifest `spec_sha256` before transfer.

Package and transfer only the generated profile:

```bash
tar --sort=name --owner=0 --group=0 --numeric-owner \
  -czf /tmp/speccon-devpm-read.tar.gz \
  -C output/speccon/profiles devpm-read
scp /tmp/speccon-devpm-read.tar.gz speccon-mcp:/tmp/
```

On the remote host, install Python and the generated artifact without cloning the repository or copying the private OpenAPI spec:

```bash
sudo install -d -o root -g mcp-speccon -m 0750 /opt/mcp-anything/output/speccon/profiles
sudo python3 -m venv /opt/mcp-anything/venv
sudo /opt/mcp-anything/venv/bin/pip install "fastmcp>=2.0" "httpx>=0.27"
sudo tar -xzf /tmp/speccon-devpm-read.tar.gz \
  -C /opt/mcp-anything/output/speccon/profiles
sudo chown -R mcp-speccon:mcp-speccon /opt/mcp-anything
```

The remote manifest must match the workstation manifest byte-for-byte. The remote host must contain the generated server and copied `mcp_runtime.py`, but not `specs/speccon-openapi.json` or the generator source.

- [ ] **Step 4: Install the remote secret file**

Create `/etc/mcp-anything/speccon-devpm.env` with the following non-secret structure, filling credential values from the approved secret store:

```dotenv
SPECCON_DEVPM_BASE_URL=https://prod-erp-backend.azurewebsites.net
SPECCON_DEVPM_EMAIL=
SPECCON_DEVPM_PASSWORD=
SPECCON_DEVPM_API_KEY=
SPECCON_DEVPM_ALLOW_WRITES=false
SPECCON_DEVPM_ALLOWED_TAGS=DevPmActivity,DevPmAudit,DevPmBugClaim,DevPmBugTriage,DevPmDashboard,DevPmDocumentImports,DevPmEpics,DevPmEvents,DevPmLabels,DevPmLearners,DevPmMetrics,DevPmNotifications,DevPmPhases,DevPmPoker,DevPmProjectPhases,DevPmProjects,DevPmQuestions,DevPmReleaseNotes,DevPmReports,DevPmSettings,DevPmSprints,DevPmSquads,DevPmSubFeatures,DevPmTeam,DevPmTicketSubtasks,DevPmTickets,DevPmUserPreferences
SPECCON_DEVPM_ALLOWED_OPERATIONS=
SPECCON_DEVPM_DENIED_OPERATIONS=
```

Set ownership and permissions:

```bash
sudo chown root:mcp-speccon /etc/mcp-anything/speccon-devpm.env
sudo chmod 0640 /etc/mcp-anything/speccon-devpm.env
```

- [ ] **Step 5: Create the stdio wrapper**

Create `/usr/local/bin/speccon-devpm-mcp` with exactly this behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail
set -a
source /etc/mcp-anything/speccon-devpm.env
set +a

exec /opt/mcp-anything/venv/bin/python \
  /opt/mcp-anything/output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py
```

Install it as root-owned and executable:

```bash
sudo chown root:root /usr/local/bin/speccon-devpm-mcp
sudo chmod 0755 /usr/local/bin/speccon-devpm-mcp
```

The wrapper must not print banners, credentials, health messages, or shell diagnostics to stdout. MCP protocol traffic owns stdout.

- [ ] **Step 6: Verify the remote process locally on the host**

Run a non-mutating import and MCP initialization check on the remote host using the wrapper. The check must confirm the server name `speccon-crm-devpm-read`, protocol initialization, and exactly 139 tools. Do not call any tool that reaches the production API during this step; tool listing is sufficient.

Expected result:

```text
server = speccon-crm-devpm-read
tools = 139
methods = GET only
```

---

### Task 2: Lock down SSH access over Tailscale

**Files:**
- Modify: remote SSH/Tailscale ACL configuration
- Modify: remote user authorization state
- Do not modify: MCP server source or generated artifacts

**Interfaces:**
- The local client invokes `ssh -T speccon-mcp /usr/local/bin/speccon-devpm-mcp`.
- The remote account exposes only the read-only MCP wrapper and has no write capability.

- [ ] **Step 1: Define the local SSH host alias**

Add an entry to the development workstation's `~/.ssh/config`:

```sshconfig
Host speccon-mcp
    HostName speccon-mcp
    User mcp-speccon
    BatchMode yes
    RequestTTY no
    PermitLocalCommand no
    ConnectTimeout 10
```

Use the stable Tailscale DNS name or tailnet IP assigned to the host. Do not use a public address.

- [ ] **Step 2: Install a dedicated SSH key**

Create or select a key used only for this MCP connection. Install its public key for `mcp-speccon` and restrict it with `no-pty`, `no-agent-forwarding`, `no-port-forwarding`, and `no-X11-forwarding`. For normal SSH over Tailscale, add the forced command `command="/usr/local/bin/speccon-devpm-mcp"` to the authorized-key entry. If the environment uses Tailscale SSH instead, express the equivalent restrictions through the Tailscale SSH policy.

- [ ] **Step 3: Test the restricted SSH path**

From the workstation:

```bash
ssh -T speccon-mcp /usr/local/bin/speccon-devpm-mcp
```

The process should remain attached waiting for MCP input. Stop it with `Ctrl-C`; do not interpret the lack of human-readable output as failure. Confirm separately that the account cannot use `sudo`, create port forwards, or read `/etc/mcp-anything/speccon-devpm.env` as an unrelated user.

- [ ] **Step 4: Confirm Tailscale ACL behavior**

From an approved device, verify TCP/22 access and MCP initialization. From a non-approved device or ACL identity, verify SSH is denied. Record the ACL rule and the test result in the deployment log.

---

### Task 3: Connect the local agent through SSH-backed MCP stdio

**Files:**
- Modify: `~/.config/Claude/claude_desktop_config.json` or the selected MCP client's configuration
- Reference: `/opt/mcp-anything/output/speccon/profiles/devpm-read/mcp_config.json`

**Interfaces:**
- The MCP client launches `ssh` locally.
- SSH launches `/usr/local/bin/speccon-devpm-mcp` remotely.
- MCP messages flow unchanged through SSH stdin/stdout.

- [ ] **Step 1: Add the client configuration**

For Claude Desktop, add this server entry to `~/.config/Claude/claude_desktop_config.json`:

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

Do not add backend credentials to this JSON. They belong only in the remote environment file.

- [ ] **Step 2: Restart the MCP client**

Fully restart the MCP client so it reloads the configuration and starts a fresh SSH process. Confirm the client reports `speccon-remote` as connected and lists 139 tools.

- [ ] **Step 3: Exercise a harmless read operation**

Ask the agent to list or inspect a known Dev PM read-only record. Use an operation whose generated inventory entry has method `GET`. Confirm the request reaches the backend with the remote service account and the response is returned through MCP.

Do not test POST, PUT, PATCH, or DELETE in the first deployment.

- [ ] **Step 4: Verify failure behavior**

Test these non-mutating failure cases:

1. Stop the remote host: the client reports an SSH/MCP connection failure.
2. Remove the remote credential temporarily: the tool reports an authentication failure without exposing the password.
3. Reconnect after restoring the credential: the client reinitializes and lists tools again.

Restore the secret file after the negative test and verify the final connection once more.

---

### Task 4: Add operational monitoring and rollback

**Files:**
- Create: `/var/log/mcp-anything/` or the selected remote logging destination
- Create: deployment record containing repository commit and manifest hash
- Modify: Tailscale ACL and SSH key state only when access changes are required

**Interfaces:**
- MCP protocol remains on stdout.
- SSH diagnostics and wrapper failures are captured on stderr or the remote host's SSH/session logs.
- Rollback does not change Speccon backend data.

- [ ] **Step 1: Record deployment identity**

Record:

```text
repository commit: record the output of `git rev-parse HEAD`
generated profile: speccon-crm-devpm-read
generated tool count: 139
allow_writes: false
env_prefix: SPECCON_DEVPM
spec_sha256: c03226874ce1441f33d557aab868072943e8a44ba7780afa567ed5e383b75b48
```

Store this record outside the secret file and outside the repository checkout.

- [ ] **Step 2: Define the incident checks**

When the client fails, check in this order:

```bash
tailscale status
ssh -T speccon-mcp /usr/local/bin/speccon-devpm-mcp
ssh speccon-mcp /opt/mcp-anything/venv/bin/python -c 'import fastmcp, httpx; print("dependencies ok")'
```

Then inspect the remote SSH/session stderr. Never enable verbose logging that prints environment variables or request credentials.

- [ ] **Step 3: Roll back the client entry**

Remove the `speccon-remote` entry from the local MCP client configuration and restart the client. This immediately prevents new agent sessions from reaching the remote MCP server.

- [ ] **Step 4: Disable remote access**

For a full rollback, remove the dedicated SSH key or disable the Tailscale ACL rule, then stop using the `mcp-speccon` account. Leave the repository checkout and generated artifacts intact for forensic comparison unless a separate host-retirement procedure requires removal.

- [ ] **Step 5: Restore the prior artifact**

If a generator regression is found, check out the previously recorded repository commit, reinstall the virtual environment only if dependencies changed, and regenerate the read-only Dev PM profile. Re-run the exact 139-tool initialization check before restoring the client entry.

---

### Task 5: Add automated deployment verification

**Files:**
- Create: `ops/remote_mcp_smoke.py` or an equivalent deployment-only test script outside the production server artifact
- Reference: `tests/test_runtime.py`
- Reference: `output/speccon/profiles/devpm-read/tools_inventory.json`

**Interfaces:**
- Consumes the existing MCP stdio contract through `ssh`.
- Produces a non-mutating verification result with server name, protocol version, tool count, and method set.

- [ ] **Step 1: Implement the SSH MCP smoke test**

Use FastMCP's `Client` and `StdioTransport` with:

```python
StdioTransport(
    command="ssh",
    args=["-T", "speccon-mcp", "/usr/local/bin/speccon-devpm-mcp"],
    log_file=Path("/tmp/speccon-remote-mcp.log"),
)
```

The script must:

1. Initialize the MCP session.
2. Assert `serverInfo.name == "speccon-crm-devpm-read"`.
3. List tools.
4. Assert `len(tools) == 139`.
5. Read the checked-in inventory and assert every method is `GET`.
6. Exit nonzero on any mismatch.
7. Never call a tool or send a backend mutation.

- [ ] **Step 2: Run the smoke test from an approved workstation**

Run it after every remote artifact or credential rotation. Capture the output and the remote commit/manifest identity in the deployment record.

- [ ] **Step 3: Run the existing regression suite before promotion**

From the repository checkout:

```bash
source venv/bin/activate
python3 -m pytest tests/ -q
python3 -m py_compile \
  mcp_anything/generator.py \
  output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py
```

Promotion requires zero test failures and zero compilation errors.

---

### Task 6: Optional later phase — Streamable HTTP through Tailscale Serve

**Files:**
- Create: `/etc/systemd/system/speccon-devpm-mcp.service`
- Create: `/etc/mcp-anything/speccon-devpm-http.env`
- Modify: Tailscale Serve configuration
- Modify: remote MCP client configuration to use a URL

**Interfaces:**
- The generated server remains unchanged and reads FastMCP transport settings from `FASTMCP_*` environment variables.
- The endpoint is `/mcp` on localhost and is published only through Tailscale Serve.

Do not implement this phase unless multiple agents need a shared URL or an agent client cannot launch SSH.

- [ ] **Step 1: Create the HTTP environment file**

Use:

```dotenv
FASTMCP_TRANSPORT=streamable-http
FASTMCP_HOST=127.0.0.1
FASTMCP_PORT=8000
FASTMCP_HTTP_HOST_ORIGIN_PROTECTION=true
FASTMCP_HTTP_ALLOWED_HOSTS=["speccon-mcp","127.0.0.1"]
SPECCON_DEVPM_ALLOW_WRITES=false
```

Add the same remote backend credential variables used by the SSH profile. Keep the file mode `0640` and ownership restricted to the service account.

- [ ] **Step 2: Create the systemd service**

The service must use `EnvironmentFile=/etc/mcp-anything/speccon-devpm-http.env`, run as `mcp-speccon`, restart on failure, and execute:

```text
/opt/mcp-anything/venv/bin/python /opt/mcp-anything/output/speccon/profiles/devpm-read/speccon_crm_devpm_read_server.py
```

Bind only to `127.0.0.1`; do not bind directly to a public interface.

- [ ] **Step 3: Publish through Tailscale Serve**

Publish only to the tailnet:

```bash
tailscale serve --https=443 http://127.0.0.1:8000
```

Do not use Tailscale Funnel. Restrict access with Tailscale ACLs and verify the HTTPS endpoint is inaccessible from outside the tailnet.

- [ ] **Step 4: Switch only compatible clients to the URL**

Run `tailscale serve status` and use the HTTPS URL it prints, appending `/mcp`, in the compatible client's remote MCP URL field. Keep the SSH entry until the HTTP endpoint has passed initialization, tool-count, ACL, and rollback checks.


- [ ] **Step 5: Verify HTTP-specific controls**

Verify:

1. MCP initialization succeeds over HTTPS.
2. Exactly 139 tools are listed.
3. Requests from an unauthorized tailnet identity fail.
4. The endpoint is not reachable from the public internet.
5. `SPECCON_DEVPM_ALLOW_WRITES=false` remains enforced.
6. Removing the Tailscale Serve configuration immediately removes access.

---

## Completion Checklist

- [ ] Remote Tailscale host has the pinned repository commit and matching generated manifest.
- [ ] Dedicated `mcp-speccon` account exists without administrative access.
- [ ] Secret file is remote-only with restrictive permissions.
- [ ] Wrapper launches the exact read-only generated profile.
- [ ] SSH access is limited to approved tailnet identities.
- [ ] Local client connects through `ssh -T speccon-mcp`.
- [ ] MCP initialization reports `speccon-crm-devpm-read`.
- [ ] Exactly 139 tools are visible.
- [ ] Inventory and runtime checks confirm `GET`-only exposure.
- [ ] Existing tests and compilation checks pass.
- [ ] No production-mutating request was used during verification.
- [ ] Rollback steps have been tested or explicitly recorded.
- [ ] HTTP/Tailscale Serve remains deferred unless multi-client access requires it.
