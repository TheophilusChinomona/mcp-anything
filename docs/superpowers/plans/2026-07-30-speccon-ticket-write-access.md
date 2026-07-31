# Speccon Dev PM Ticket Write Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the live read-only Speccon Dev PM MCP profile with an explicit ticket-workflow write profile that preserves reads, excludes deletes and unrelated writes, and teaches agents when to confirm high-impact mutations.

**Architecture:** Extend the reusable generator/runtime policy to support a complete operation allowlist plus a method allowlist. Generate a new `speccon-crm-devpm-write` artifact containing the 139 existing GET tools and 22 canonical ticket/subtask write tools, while denying six delete operations. Validate and archive the current read-only profile before switching the existing Tailscale MCP endpoint to the write artifact.

**Tech Stack:** Python 3.10+, OpenAPI analyzer, FastMCP 3.x, `httpx`, generated stdio/Streamable HTTP server, Tailscale-bound MCP endpoint, pytest.

## Global Constraints

- Keep `speccon-erp` at `http://100.102.160.49:8000/mcp`; replace the artifact behind that registration rather than adding a second client registration.
- Keep credentials outside Git, MCP JSON, prompts, generated artifacts, and logs.
- Keep the server bound to the Tailscale interface; do not add a public listener, Funnel, public DNS, or a new firewall exposure.
- Preserve all 139 current Dev PM GET tools.
- Expose exactly these 22 canonical write operation IDs and no other non-GET operations:

```text
post_api_devpm_Tickets_Create
put_api_devpm_Tickets_Update
post_api_devpm_Tickets_AddCollaborator
post_api_devpm_Tickets_RemoveCollaborator
post_api_devpm_Tickets_Approve
post_api_devpm_Tickets_Delegate
post_api_devpm_Tickets_FlagForReview
patch_api_devpm_Tickets_PatchReviewFlag
post_api_devpm_Tickets_Park
post_api_devpm_Tickets_QaReject
post_api_devpm_Tickets_BatchUpdatePlanningStatus
post_api_devpm_Tickets_CreateComment
post_api_devpm_Tickets_CreateSubtask
put_api_devpm_Tickets_UpdateSubtask
post_api_devpm_Tickets_AddLink
post_api_devpm_Tickets_UploadAttachment
post_api_devpm_Tickets_CreateQuestion
post_api_devpm_Tickets_ResolveQuestion
post_api_devpm_Tickets_Subscribe
post_api_devpm_TicketSubtasks_Create
put_api_devpm_TicketSubtasks_Update
post_api_devpm_TicketSubtasks_Complete
```

- Keep these six operation IDs denied:

```text
delete_api_devpm_Tickets_Delete
delete_api_devpm_Tickets_DeleteSubtask
delete_api_devpm_Tickets_DeleteLink
delete_api_devpm_Tickets_DeleteAttachment
delete_api_devpm_Tickets_Unsubscribe
delete_api_devpm_TicketSubtasks_Delete
```

- The effective runtime operation allowlist is the sorted union of the 139 GET operation IDs and the 22 write operation IDs; it is not limited to the write IDs.
- Automatic verification must not call a production write. An approved smoke write is a separate operator step after all non-mutating checks pass.
- Rollback must restore the archived read-only profile with `SPECCON_DEVPM_ALLOW_WRITES=false` and `SPECCON_DEVPM_ALLOWED_METHODS=GET`.

---

## File map

| File | Responsibility |
|---|---|
| `mcp_anything/generator.py` | Normalize and apply method/operation policies; emit policy metadata, config, inventory, and manifest. |
| `mcp_anything/runtime.py` | Enforce method, operation, tag, and write policies at request time. |
| `ops/generate_devpm_profile.py` | Generate the existing read profile or the explicit ticket-workflow write profile from the private local spec. |
| `tests/test_devpm_profile.py` | Fixture coverage for canonical write selection, duplicate alias exclusion, delete exclusion, manifest fields, and profile naming. |
| `tests/test_generator.py` | Generator policy and artifact-contract regression tests. |
| `tests/test_runtime.py` | Runtime policy tests, including allowed methods and denied operations. |
| `tests/test_generated_artifact.py` | Generated server/runtime compilation and import tests. |
| `docs/agent-prompts/speccon-erp-mcp-setup.md` | Agent connection, write confirmation, safety, and error-handling instructions. |
| `README.md` | Current installation, agent setup, and remote profile documentation. |
| `docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md` | Operator runbook updated for write-profile rollout and read-only rollback. |
| `output/speccon/profiles/` | Local ignored generated artifacts; preserve the current read profile before replacement. |
| `/home/theo-zo/.config/mcp-anything/speccon-devpm.env` | Host-local credentials and active policy; never commit or paste its contents. |
| `/home/theo-zo/.local/bin/speccon-devpm-http` | Host-local wrapper that sources the secure env file and launches the selected generated server. |

---

### Task 1: Harden generator and runtime policy handling

**Files:**
- Modify: `mcp_anything/generator.py`
- Modify: `mcp_anything/runtime.py`
- Test: `tests/test_generator.py`
- Test: `tests/test_runtime.py`
- Test: `tests/test_generated_artifact.py`

**Interfaces:**
- `MCPServerGenerator.__init__` accepts `allowed_methods: Iterable[str] | None` in addition to `allow_writes`, `allowed_tags`, `allowed_operations`, and `denied_operations`.
- `CapabilityPolicy.__init__` and `CapabilityPolicy.from_env()` accept and enforce `allowed_methods` / `SPECCON_DEVPM_ALLOWED_METHODS`.
- The generator emits the normalized policy in `.env.example`, `mcp_config.json`, `generation_manifest.json`, and `tools_inventory.json` without exposing credentials.

- [ ] **Step 1: Add failing policy tests**

Add tests that construct a generator with:

```python
allowed_methods={"GET", "POST", "PUT", "PATCH"}
allowed_operations={"read_project", "create_ticket"}
denied_operations={"delete_ticket"}
allow_writes=True
```

Assert that only the two allowed operation IDs are generated, a DELETE endpoint is absent, and the manifest/config contain the normalized method and operation policies. Add runtime tests asserting:

```python
CapabilityPolicy.from_env("SPECCON_DEVPM").check("GET", "read_project")
CapabilityPolicy.from_env("SPECCON_DEVPM").check("POST", "create_ticket")
```

succeed while DELETE and an operation outside the allowlist raise `CapabilityDenied`.

- [ ] **Step 2: Run the focused tests and confirm the new assertions fail**

Run:

```bash
/home/theo-zo/dev/mcp-anything/venv/bin/pytest -q \
  tests/test_generator.py tests/test_runtime.py tests/test_generated_artifact.py
```

Expected: the new method/operation policy assertions fail against the unmodified behavior.

- [ ] **Step 3: Normalize and apply generator policy**

Normalize all iterable policy inputs to uppercase sets where appropriate:

```python
self.allowed_methods = {
    method.upper() for method in (allowed_methods or ()) if method
}
self.allowed_operations = {operation for operation in (allowed_operations or ()) if operation}
self.denied_operations = {operation for operation in (denied_operations or ()) if operation}
```

Filter an endpoint only when all of these conditions pass:

1. Its method is in `allowed_methods` when that set is non-empty.
2. If `allow_writes` is false, its method is one of the generic safe methods.
3. Its operation ID is in `allowed_operations` when that set is non-empty.
4. Its operation ID is not in `denied_operations`.
5. Its tags satisfy `allowed_tags` when tags are configured.

Emit sorted policy values consistently in generated config, environment template, inventory metadata, and manifest metadata. Keep one manifest write and copy the complete `mcp_anything.runtime` source beside every generated server.

- [ ] **Step 4: Enforce the same policy in the copied runtime**

Parse comma-separated `SPECCON_DEVPM_ALLOWED_METHODS`, `SPECCON_DEVPM_ALLOWED_OPERATIONS`, and `SPECCON_DEVPM_DENIED_OPERATIONS` in `CapabilityPolicy.from_env()`. Check the explicit method and operation allowlists before the generic `SAFE_METHODS` write guard. Do not add automatic retries for failed write requests.

- [ ] **Step 5: Run the focused tests and compile generated artifacts**

Run:

```bash
/home/theo-zo/dev/mcp-anything/venv/bin/pytest -q \
  tests/test_generator.py tests/test_runtime.py tests/test_generated_artifact.py
/home/theo-zo/dev/mcp-anything/venv/bin/python -m py_compile \
  mcp_anything/generator.py mcp_anything/runtime.py
```

Expected: all focused tests pass and both modules compile.

- [ ] **Step 6: Commit the policy foundation**

```bash
git add mcp_anything/generator.py mcp_anything/runtime.py \
  tests/test_generator.py tests/test_runtime.py tests/test_generated_artifact.py
git commit -m "feat: enforce explicit Dev PM operation policies"
```

---

### Task 2: Add explicit read/write profile generation

**Files:**
- Modify: `ops/generate_devpm_profile.py`
- Test: `tests/test_devpm_profile.py`
- Reference: `specs/speccon-openapi.json` (local private input only; never commit or copy it)

**Interfaces:**
- Preserve the existing default read profile behavior.
- Add `build_profile(spec: Path, output: Path, profile: str = "read") -> dict`.
- Add a CLI option `--profile` with choices `read` and `write`, default `read`.
- The write profile uses `server_name="speccon-crm-devpm-write"`, `env_prefix="SPECCON_DEVPM"`, `allow_writes=True`, and `allowed_methods={"GET", "POST", "PUT", "PATCH"}`.
- The generated write result contains 161 tools: 139 GET tools plus 22 canonical ticket/subtask write tools.

- [ ] **Step 1: Extend the fixture with duplicate aliases and unrelated writes**

Update `tests/test_devpm_profile.py` with a minimal OpenAPI fixture containing:

- At least one Dev PM GET endpoint.
- Canonical `/api/devpm/Tickets/*` write endpoints from the approved 22-operation list.
- Duplicate `/api/devpm/DevPmTickets/*` aliases.
- The six denied DELETE operations.
- An unrelated write endpoint such as `/api/devpm/Projects/Create`.
- A non-Dev PM write endpoint.

- [ ] **Step 2: Add failing write-profile assertions**

Assert that `build_profile(..., profile="write")` produces:

```python
manifest["server_name"] == "speccon-crm-devpm-write"
manifest["allow_writes"] is True
manifest["allowed_methods"] == ["GET", "PATCH", "POST", "PUT"]
```

Also assert that canonical ticket writes are present, duplicate aliases and unrelated writes are absent, all DELETE methods are absent, and every emitted tool has an operation ID in the combined read/write allowlist.

- [ ] **Step 3: Implement the profile mode**

Define immutable constants for the 22 approved write IDs and six denied IDs. For `profile="write"`:

1. Extract all allowlisted Dev PM GET operation IDs.
2. Union those IDs with the 22 approved write IDs.
3. Pass the union as `allowed_operations`.
4. Pass the six delete IDs as `denied_operations`.
5. Pass `allowed_methods={"GET", "POST", "PUT", "PATCH"}`.
6. Set the write profile name and metadata.
7. Reject unknown profile names with `ValueError`.

Do not load, copy, or embed the private OpenAPI spec in generated output.

- [ ] **Step 4: Run profile tests and a local private-spec generation check**

Run:

```bash
/home/theo-zo/dev/mcp-anything/venv/bin/pytest -q tests/test_devpm_profile.py
/home/theo-zo/dev/mcp-anything/venv/bin/python ops/generate_devpm_profile.py \
  --profile write \
  --spec specs/speccon-openapi.json \
  --output /tmp/speccon-devpm-write-check
```

Assert from `/tmp/speccon-devpm-write-check/generation_manifest.json` that the tool count is 161, methods are exactly GET/POST/PUT/PATCH, and no private spec file exists in the output directory.

- [ ] **Step 5: Commit profile generation**

```bash
git add ops/generate_devpm_profile.py tests/test_devpm_profile.py
git commit -m "feat: generate scoped Dev PM ticket write profile"
```

---

### Task 3: Update agent and user-facing instructions

**Files:**
- Modify: `docs/agent-prompts/speccon-erp-mcp-setup.md`
- Modify: `README.md`
- Test: `tests/test_devpm_profile.py` (prompt/config safety assertions)

**Interfaces:**
- The client alias remains `speccon-erp`.
- The prompt must describe the replacement profile as write-capable but ticket-scoped.
- Credentials remain server-side and absent from all documentation.

- [ ] **Step 1: Update the agent prompt**

Replace the read-only prohibition with these exact behavioral rules:

- Routine ticket creation, comments, and ordinary subtask operations may proceed after parameter validation.
- The agent must request explicit confirmation before assignment/delegation, collaborator changes, approvals, parking, QA rejection, review-flag changes, batch planning updates, attachments, links, subscriptions, question resolution, or ambiguous writes.
- The agent must never call the six denied delete operations.
- The agent must not automatically retry failed writes.
- The agent must verify tool method and operation ID before every write.

Keep the endpoint, Tailscale, credential, and error-handling instructions current. Do not place credentials in the prompt.

- [ ] **Step 2: Update README deployment and agent sections**

Document:

```text
MCP server: speccon-crm-devpm-write
MCP alias: speccon-erp
Expected tools: 161
Methods: GET, POST, PUT, PATCH
Deletes: excluded
```

Explain that the profile remains restricted to ticket/subtask workflow writes and that confirmation is required for high-impact mutations. Keep rollback instructions for restoring the 139-tool GET-only profile.

- [ ] **Step 3: Verify documentation safety**

Run:

```bash
python3 -c 'from pathlib import Path; text=Path("README.md").read_text()+Path("docs/agent-prompts/speccon-erp-mcp-setup.md").read_text(); assert "Theo0099" not in text; assert "theoc@speccon.co.za" not in text; print("documentation secret scan: PASS")'
```

- [ ] **Step 4: Commit documentation**

```bash
git add README.md docs/agent-prompts/speccon-erp-mcp-setup.md
 git commit -m "docs: document scoped Dev PM writes"
```

---

### Task 4: Update the remote deployment runbook

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md`
- Do not commit: `/home/theo-zo/.config/mcp-anything/speccon-devpm.env`
- Do not commit: generated artifacts under `output/speccon/profiles/`

**Interfaces:**
- The remote wrapper continues sourcing `/home/theo-zo/.config/mcp-anything/speccon-devpm.env`.
- The wrapper launches the replacement generated server without printing diagnostics to stdout.
- The client URL remains `http://100.102.160.49:8000/mcp`.

- [ ] **Step 1: Update deployment values and policy**

Change the runbook to identify:

```text
Profile: speccon-crm-devpm-write
Expected tools: 161
Expected methods: GET, POST, PUT, PATCH
SPECCON_DEVPM_ALLOW_WRITES=true
SPECCON_DEVPM_ALLOWED_METHODS=GET,POST,PUT,PATCH
```

Document the combined operation allowlist and six-operation delete denylist without adding credentials.

- [ ] **Step 2: Add the rollback archive procedure**

Before changing the active profile, archive the current read-only profile and manifest:

```bash
archive=/tmp/speccon-devpm-read-rollback-$(date +%Y%m%d%H%M%S).tar.gz
tar --sort=name --owner=0 --group=0 --numeric-owner \
  -czf "$archive" \
  -C /home/theo-zo/dev/mcp-anything/output/speccon/profiles devpm-read
```

Record the archive path, old manifest SHA-256, and current process identity without recording credentials.

- [ ] **Step 3: Generate and validate the write artifact**

Run the Task 2 write-profile command into `output/speccon/profiles/devpm-write`, validate the manifest and compiled runtime, and only then update the wrapper to launch `devpm-write`.

- [ ] **Step 4: Apply the secure host policy**

Update the existing mode-600 environment file using the explicit policy values. Preserve the existing credentials without printing or committing them. Do not apply the policy until the generated artifact checks pass.

- [ ] **Step 5: Restart the live MCP process**

Stop the current `speccon-devpm-http` process, start the wrapper-backed write profile on `100.102.160.49:8000`, and verify the process is ready before reconnecting the client.

- [ ] **Step 6: Commit only the runbook update**

```bash
git add docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md
git commit -m "docs: update Dev PM write deployment runbook"
```

---

### Task 5: Run non-mutating rollout verification

**Files:**
- Test: `tests/test_devpm_profile.py`
- Test: `tests/test_generator.py`
- Test: `tests/test_runtime.py`
- Test: `tests/test_generated_artifact.py`
- Verify: generated write profile manifest, inventory, and MCP endpoint

- [ ] **Step 1: Run the focused regression suite**

```bash
/home/theo-zo/dev/mcp-anything/venv/bin/pytest -q \
  tests/test_devpm_profile.py \
  tests/test_generator.py \
  tests/test_runtime.py \
  tests/test_generated_artifact.py
```

Require zero failures.

- [ ] **Step 2: Compile the generated profile**

```bash
/home/theo-zo/dev/mcp-anything/venv/bin/python -m py_compile \
  output/speccon/profiles/devpm-write/speccon_crm_devpm_write_server.py \
  output/speccon/profiles/devpm-write/mcp_runtime.py
```

- [ ] **Step 3: Inspect the manifest and inventory without calling the API**

Assert:

```python
manifest["server_name"] == "speccon-crm-devpm-write"
manifest["endpoint_count"] == 161
manifest["allow_writes"] is True
set(manifest["allowed_methods"]) == {"GET", "POST", "PUT", "PATCH"}
set(item["method"] for item in inventory) <= {"GET", "POST", "PUT", "PATCH"}
```

Assert every write operation is in the 22-ID allowlist and no operation is in the six-ID delete denylist.

- [ ] **Step 4: Perform MCP initialization and tool listing**

Connect to `http://100.102.160.49:8000/mcp`, list tools, and assert 161 tools. Do not call a write tool during this automated step.

- [ ] **Step 5: Obtain explicit approval for a smoke write**

Stop before any production write. Ask the user to identify a disposable or clearly intended ticket operation and explicitly approve it. Show the exact tool, target, and payload before calling. Execute once, do not retry automatically, and report only the result needed to verify the operation.

- [ ] **Step 6: Verify rollback readiness**

Confirm the read-only archive exists, its manifest is readable, and the read-only environment values are documented. Do not perform rollback unless the write rollout fails or the user requests it.

- [ ] **Step 7: Commit verification evidence only when requested**

Do not commit credentials, generated profiles, response data, or secret logs. Keep verification output local unless a sanitized deployment record is explicitly requested.

---

## Self-review checklist

Before execution, confirm:

- [ ] The profile keeps 139 GET tools and adds exactly 22 canonical writes.
- [ ] The six delete operations are absent and denied at runtime.
- [ ] The runtime operation allowlist includes reads plus approved writes, not writes alone.
- [ ] Duplicate `DevPmTickets` aliases are excluded.
- [ ] Agent confirmation rules cover high-impact mutations.
- [ ] No credentials appear in source, documentation, generated JSON, or commits.
- [ ] Automated verification performs no production write.
- [ ] Rollback restores the archived 139-tool GET-only profile.
