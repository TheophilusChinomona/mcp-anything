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
SPECCON_DEVPM_ALLOWED_METHODS=GET
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

