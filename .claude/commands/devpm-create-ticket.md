---
description: "Create a Speccon Dev PM ticket via the MCP write profile: gather details, create, and assign to the requesting user with confirmation."
argument-hint: "[title]"
---

# /devpm-create-ticket — Create a DevPM ticket

Creates a ticket on the live Speccon Dev PM board through `speccon-crm-devpm-write`, then assigns it to the requesting user so it appears on their board.

## Flow

1. **Gather** (or accept as arguments): `title`, `description`, `acceptanceCriteria`, `technicalDetails`, `ticketType` (default `Bug`).
2. **Resolve project key:** `get_api_devpm_devpmprojects_getlist` → use the `ERP DevPM` project UUID (`98d8e670-78fd-4166-a5e4-b113ff02fc08` unless the user says otherwise).
3. **Confirm with the user** — show title, type, project, and summary before writing.
4. **Create:** `post_api_devpm_devpmtickets_create` with body = `CreateDevPmSnagDto`.
5. **Assign:** `put_api_devpm_devpmtickets_update` with `body = {"assigneeUserId": <user id>}` — resolve the user id from `get_api_devpm_devpmteam_getmembers` (by email). This is a confirmation-required write; the create step already confirmed the ticket, so confirm the assignment separately if the user hasn't named themselves.
6. **Verify:** `get_api_devpm_devpmtickets_getbykey` → report ticket number, title, assignee, status.

## Report

```
Created #<ticketNumber>: <title>
Type: <ticketType> | Project: <project> | Status: <status>
Assigned to: <name> (<userId>)
```

## Rules

- Never pass credentials in tool args or output.
- If create succeeds but update 401s, restart `speccon-devpm-http` once and retry (stale token); report auth vs policy errors distinctly.
- Never retry automatically on ambiguous failure.
