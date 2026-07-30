# Speccon Dev PM Ticket Write Access Design

**Date:** 2026-07-30

## Goal

Replace the current read-only Speccon Dev PM MCP profile with a ticket-workflow profile that lets local agents create and manage tickets while excluding destructive delete operations and unrelated Dev PM writes.

## User decisions

- Replace the current `speccon-erp` read-only registration rather than add a second MCP registration.
- Allow the full canonical ticket and ticket-subtask workflow except deletes.
- Require agent/user confirmation before high-impact writes.
- Keep project, sprint, squad, settings, epic, label, release-note, document-import, bug-claim, and unrelated administrative writes excluded.

## Profile identity

The replacement generated profile uses:

```text
MCP server: speccon-crm-devpm-write
MCP client alias: speccon-erp
Environment prefix: SPECCON_DEVPM
Endpoint: http://100.102.160.49:8000/mcp
```

The existing endpoint and client alias remain stable. The generated artifact name changes so the capability change is visible in manifests and logs.

## Allowed methods

The profile includes all existing Dev PM GET tools plus these write methods:

```text
GET, POST, PUT, PATCH
```

DELETE is excluded by both the explicit operation allowlist and the runtime method policy.

## Explicit write allowlist

Only these canonical operation IDs are emitted as write tools:

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

The duplicate `/DevPmTickets` and `/DevPmTicketSubtasks` operation aliases are not emitted. The canonical `/Tickets` and `/TicketSubtasks` routes are the only write routes exposed.

## Explicit denylist

These destructive operations remain unavailable:

```text
delete_api_devpm_Tickets_Delete
delete_api_devpm_Tickets_DeleteSubtask
delete_api_devpm_Tickets_DeleteLink
delete_api_devpm_Tickets_DeleteAttachment
delete_api_devpm_Tickets_Unsubscribe
delete_api_devpm_TicketSubtasks_Delete
```

The generator and runtime must enforce the denylist even if a future tag or method configuration is broadened.

## Agent confirmation policy

The server enforces capability boundaries; the agent prompt enforces human confirmation behavior.

Routine writes may execute after parameter validation:

- Ticket creation.
- Comments.
- Ordinary subtask creation and completion.
- Non-workflow field updates that do not change assignment or review state.

The agent must display the exact target, operation, and intended change and ask for explicit confirmation before:

- Ticket updates that alter workflow state.
- Collaborator changes or delegation.
- Approval, parking, QA rejection, or review-flag changes.
- Batch planning-status updates.
- Attachments and links.
- Subscriptions.
- Ticket-question resolution.
- Any write whose effect cannot be summarized precisely from the supplied parameters.

The agent must not retry a failed write automatically. It must report authentication, authorization, policy, timeout, and backend errors without exposing credentials.

## Credentials and deployment

The existing server-side environment file remains outside Git with mode `0600`. It changes only in policy values. The runtime operation allowlist is the sorted union of the 139 existing GET operation IDs and the 22 write operation IDs listed above; this preserves the read surface while excluding every unrelated write. The six delete operation IDs remain in the denylist as defense in depth:

```dotenv
SPECCON_DEVPM_ALLOW_WRITES=true
SPECCON_DEVPM_ALLOWED_METHODS=GET,POST,PUT,PATCH
# Set SPECCON_DEVPM_ALLOWED_OPERATIONS to the generator-emitted sorted union of the 139 GET operation IDs and the 22 explicit write operation IDs.
SPECCON_DEVPM_DENIED_OPERATIONS=delete_api_devpm_Tickets_Delete,delete_api_devpm_Tickets_DeleteSubtask,delete_api_devpm_Tickets_DeleteLink,delete_api_devpm_Tickets_DeleteAttachment,delete_api_devpm_Tickets_Unsubscribe,delete_api_devpm_TicketSubtasks_Delete
```

The angle-bracket text above is a description of the generated value, not a literal environment value. The generator must emit the complete comma-separated operation list into the profile metadata and environment template; deployment must not leave the description text in the live environment file.

Credentials remain server-side and must not be placed in client JSON, prompts, generated artifacts, or logs.

Before replacing the live artifact, archive the current read-only profile and manifest for rollback. Rollback restores the read-only generated server and the following policy:

```dotenv
SPECCON_DEVPM_ALLOW_WRITES=false
SPECCON_DEVPM_ALLOWED_METHODS=GET
```

## Verification

Verification must be non-mutating until an explicit approved smoke write is available.

Required checks:

1. Generate the replacement profile from the trusted local OpenAPI spec.
2. Verify the manifest identifies `speccon-crm-devpm-write` and records `allow_writes=true`.
3. Verify the manifest allowed methods are exactly `GET`, `POST`, `PUT`, and `PATCH`.
4. Verify all 139 existing GET tools remain present.
5. Verify the 22 explicit write operation IDs are present.
6. Verify all six delete operation IDs are absent.
7. Verify no project, sprint, squad, settings, epic, label, release-note, document-import, bug-claim, or unrelated administrative writes are present.
8. Compile the generated server beside its copied runtime.
9. Initialize MCP and verify the expected tool count of 161 (139 reads plus 22 writes).
10. Perform no production write during automated verification.
11. If the user explicitly approves a smoke write, use a disposable or clearly identified ticket target, record the exact operation, and do not retry automatically.

## Rollback

Rollback is an artifact and process restart, not a backend data operation:

1. Stop the write-capable MCP process.
2. Restore the archived read-only profile and manifest.
3. Restore `SPECCON_DEVPM_ALLOW_WRITES=false` and `SPECCON_DEVPM_ALLOWED_METHODS=GET`.
4. Restart the MCP process.
5. Reinitialize the client and verify the 139-tool GET-only inventory.

## Non-goals

- Enabling delete operations.
- Enabling writes for projects, sprints, squads, settings, epics, labels, release notes, document imports, bug claims, or unrelated resources.
- Building a second client registration.
- Adding a public HTTP listener or changing Tailscale ACLs.
- Storing credentials in the repository or MCP client configuration.
