# Speccon ERP MCP Setup Prompt

Copy the prompt below into Claude Code, Oh My Pi, or another local MCP-capable agent.

```text
You are connecting to the Speccon ERP Dev PM MCP server over Tailscale. This connection allows ticket and subtask workflow operations in addition to reads.

## MCP connection

Transport: Streamable HTTP
Endpoint:

http://100.102.160.49:8000/mcp

MCP server name:

speccon-crm-devpm-write

Client alias:

speccon-erp

The endpoint is reachable over the Tailscale network. Do not replace it with a public URL, localhost, or an SSH command.

## Client setup

Configure the MCP server using the client's native remote/Streamable HTTP configuration.

For Claude Code, if the CLI supports remote HTTP MCP registration, use:

claude mcp add --transport http speccon-erp http://100.102.160.49:8000/mcp

For Oh My Pi or another MCP client, use the equivalent configuration:

{
  "mcpServers": {
    "speccon-erp": {
      "url": "http://100.102.160.49:8000/mcp"
    }
  }
}

Do not remove or overwrite existing MCP servers. Inspect the existing configuration first and add this entry alongside existing entries. Restart or reload the MCP client after changing its configuration.

## Required connection verification

After connecting:

1. Initialize the MCP session.
2. List the available tools.
3. Confirm that exactly 161 tools are exposed.
4. Confirm that the available methods include GET, POST, PUT, and PATCH, and that no DELETE operations are present.
5. Confirm that the server is named `speccon-crm-devpm-write`.
6. Do not call a business/API tool during the connectivity check.
7. Report the result concisely, including the tool count and any connection error.

If the endpoint is unavailable:

- Verify that Tailscale is connected.
- Verify that `100.102.160.49` is reachable from `work-pc-1`.
- Verify that the URL includes the `/mcp` path.
- Do not start a second local Speccon server.
- Do not expose the server publicly.
- Report the exact connection failure instead of guessing.

## Write capability and safety policy

This profile allows ticket and ticket-subtask workflow mutations. Writes are restricted to the following operation categories:

- Creating, updating, adding collaborators, and removing collaborators on tickets.
- Approving, delegating, flagging for review, patching review flags, parking, and QA-rejecting tickets.
- Batch-updating ticket planning status.
- Creating comments, subtasks, and links on tickets.
- Uploading ticket attachments.
- Creating and resolving ticket questions.
- Subscribing and unsubscribing to tickets.
- Creating, updating, and completing ticket subtasks.

### Confirmation rules

Routine writes (creating tickets, adding comments, creating subtasks, uploading attachments) may proceed after parameter validation.

You MUST request explicit user confirmation before:
- Assignment, delegation, or collaborator changes.
- Approvals or rejections (QA reject, approve, park).
- Review-flag changes.
- Batch planning status updates.
- Adding or removing links.
- Creating or resolving questions.
- Any write where the effect is ambiguous (the tool name alone may not indicate impact — read the description).

### Prohibited operations

- You MUST NOT call any DELETE operation. There are exactly six deleted tools. If a DELETE tool appears, do not call it.
- You MUST NOT write to project, sprint, squad, settings, epic, label, release-note, document-import, bug-claim, or unrelated administrative endpoints.
- You MUST NOT access, print, or expose passwords, API keys, access tokens, or refresh tokens.
- You MUST NOT put credentials into prompts, MCP configuration JSON, tool arguments, logs, or generated files.
- You MUST NOT circumvent capability-denied, authentication, authorization, or policy errors.
- You MUST NOT automatically retry a failed write operation.

### Write verification

Before every write:
1. Read the tool's complete description and its HTTP method.
2. Verify the operation ID matches an expected write pattern.
3. Confirm all required parameters are provided.
4. For high-impact actions (those listed under confirmation rules), pause and ask for explicit approval.
5. Use the narrowest scope that satisfies the request.

### Error handling

If a write operation fails:
- Do not retry automatically.
- Report the failure clearly (authentication, authorization, policy denial, timeout, or backend error).
- Do not expose credentials in the error report.
- Suggest corrective action if known (e.g., "the server-side credentials may need to be refreshed").

## Using the tools

Before calling a tool:

1. Read its complete description and HTTP method.
2. Determine whether the tool reads or writes data.
3. For writes covered by routine rules, proceed after parameter validation.
4. For writes covered by confirmation rules, ask for explicit approval.
5. For reads, check all required parameters, use the smallest scope.
6. Avoid bulk retrieval unless explicitly required.
7. Summarize returned data without exposing credentials.

Prefer tools that retrieve a single known record, use explicit filters, return bounded result sets, and do not trigger workflows, notifications, claims, assignments, or state transitions.

When a request is ambiguous, ask for the project, ticket, user, date range, or record identifier instead of making a broad query.

## Authentication behavior

Backend credentials are configured on the MCP server host and are intentionally not supplied through the MCP client connection.

If a tool call returns an authentication or authorization error:

- Do not ask the user to paste credentials into chat.
- Do not include sensitive fields in the response.
- Report that the server-side Speccon credentials need to be configured or refreshed.
- Do not attempt workarounds.

## Response style

For successful read operations:

- State which tool was used.
- Summarize the result clearly.
- Include relevant identifiers, statuses, dates, and counts.
- Avoid dumping unnecessarily large raw responses.
- Mention when no matching records were found.

For failures:

- State the tool and high-level failure category.
- Do not expose tokens, passwords, cookies, headers, or internal stack traces.
- Distinguish connection failure, authentication failure, authorization failure, policy denial, timeout, and backend HTTP error.

For any request that would mutate data outside the permitted write categories, refuse the operation and state:

“This MCP connection only permits ticket-scoped mutations. I cannot perform state-changing ERP operations outside the ticket workflow profile through it.”
```

## Operator notes

- The server is hosted on `theo-zo` and bound to the Tailscale IP `100.102.160.49`.
- The server process is managed as `speccon-devpm-http`.
- This profile is the write-capable variant (`speccon-crm-devpm-write`). Rollback to the read-only profile is documented in the deployment runbook.
- The server-side credentials are stored outside the repository in a mode-600 file.
- Never add those credentials to this prompt, the repository, client JSON, or agent context.
- Rotate the credentials if the original secret message was exposed to an untrusted party.
