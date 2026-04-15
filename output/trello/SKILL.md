---
name: trello
description: Agent skill for using the Trello REST API MCP tools. Covers all 22 endpoints with workflows, error handling, and conventions.
version: 1.0.0
author: mcp-anything
metadata:
  hermes:
    tags: [mcp, api, trello]
    source: openapi-spec
---

# Trello REST API — Agent Skill

This skill defines how to use the **trello** MCP tools effectively.

## Overview

**API:** Trello REST API v1.0.0
**Base URL:** `https://api.trello.com/1`
**Total Tools:** 22

### Tool Groups

- **Boards** (8 tools): `getmemberboards`, `getboard`, `updateboard`, `deleteboard`, `createboard`, `getboardlists`, `getboardcards`, `createboardlabel`
- **Cards** (6 tools): `getboardcards`, `getlistcards`, `getcard`, `updatecard`, `deletecard`, `createcard`
- **Labels** (4 tools): `createboardlabel`, `getlabel`, `updatelabel`, `deletelabel`
- **Lists** (5 tools): `getboardlists`, `getlist`, `updatelist`, `createlist`, `getlistcards`
- **Members** (3 tools): `getmymember`, `getmember`, `getmemberboards`
- **Search** (1 tools): `search`

## Tools Reference

Use these tools to interact with the API. Each tool maps to an API endpoint.

### `getmymember`
**GET** `/members/me`

Get current authenticated member

**Parameters:**
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `getmember`
**GET** `/members/{id}`

Get a member by ID or username

**Parameters:**
- `id` (string, path, required): Member ID or username
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `getmemberboards`
**GET** `/members/{id}/boards`

Get all boards for a member

**Parameters:**
- `id` (string, path, required): Member ID or username
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")
- `filter` (string, query, optional): filter — one of: 'all', 'closed', 'none', 'open', 'starred', 'unpinned' (default: open)

### `getboard`
**GET** `/boards/{id}`

Get a board by ID

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `updateboard`
**PUT** `/boards/{id}`

Update a board

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `deleteboard`
**DELETE** `/boards/{id}`

Delete a board

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

### `createboard`
**POST** `/boards`

Create a new board

**Parameters:**
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `getboardlists`
**GET** `/boards/{id}/lists`

Get all lists on a board

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `filter` (string, query, optional): filter — one of: 'all', 'closed', 'none', 'open' (default: open)
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `getboardcards`
**GET** `/boards/{id}/cards`

Get all cards on a board

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `createboardlabel`
**POST** `/boards/{id}/labels`

Create a label on a board

**Parameters:**
- `id` (string, path, required): Board ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `getlist`
**GET** `/lists/{id}`

Get a list by ID

**Parameters:**
- `id` (string, path, required): List ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `updatelist`
**PUT** `/lists/{id}`

Update a list (rename, archive, move)

**Parameters:**
- `id` (string, path, required): List ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `createlist`
**POST** `/lists`

Create a new list on a board

**Parameters:**
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `getlistcards`
**GET** `/lists/{id}/cards`

Get all cards in a list

**Parameters:**
- `id` (string, path, required): List ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `getcard`
**GET** `/cards/{id}`

Get a card by ID

**Parameters:**
- `id` (string, path, required): Card ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `fields` (string, query, optional): Comma-separated list of fields to return (e.g. "name,id,desc")

### `updatecard`
**PUT** `/cards/{id}`

Update a card (rename, move, add labels, set due date, etc.)

**Parameters:**
- `id` (string, path, required): Card ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `deletecard`
**DELETE** `/cards/{id}`

Delete a card

**Parameters:**
- `id` (string, path, required): Card ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

### `createcard`
**POST** `/cards`

Create a new card in a list

**Parameters:**
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `getlabel`
**GET** `/labels/{id}`

Get a label by ID

**Parameters:**
- `id` (string, path, required): Label ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

### `updatelabel`
**PUT** `/labels/{id}`

Update a label (rename, change color)

**Parameters:**
- `id` (string, path, required): Label ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

**Request Body:** JSON object (pass as `body` parameter)

### `deletelabel`
**DELETE** `/labels/{id}`

Delete a label from a board

**Parameters:**
- `id` (string, path, required): Label ID
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token

### `search`
**GET** `/search`

Search across boards, cards, and members

**Parameters:**
- `key` (string, query, required): Trello API key
- `token` (string, query, required): Trello API token
- `query` (string, query, required): Search query string
- `idorganizations` (string, query, optional): Comma-separated org IDs to limit search
- `idboards` (string, query, optional): Comma-separated board IDs to limit search
- `modeltypes` (string, query, optional): Comma-separated model types to search — one of: 'actions', 'boards', 'cards', 'members', 'organizations'
- `board_fields` (string, query, optional): Fields for board results
- `cards_limit` (integer, query, optional): Max card results (default: 10)
- `boards_limit` (integer, query, optional): Max board results (default: 10)


## Common Workflows

### CRUD Operations

**boards:**
2. `getboard` — Get a specific boards by ID
3. `createboard` — Create a new boards
4. `updateboard` — Update an existing boards
5. `deleteboard` — Delete a boards

**lists:**
1. `createlist` — List all lists
2. `getlist` — Get a specific lists by ID
3. `createlist` — Create a new lists
4. `updatelist` — Update an existing lists

**cards:**
1. `getlistcards` — List all cards
2. `getcard` — Get a specific cards by ID
3. `createcard` — Create a new cards
4. `updatecard` — Update an existing cards
5. `deletecard` — Delete a cards

**labels:**
2. `getlabel` — Get a specific labels by ID
3. `createboardlabel` — Create a new labels
4. `updatelabel` — Update an existing labels
5. `deletelabel` — Delete a labels

### Search & Filter

- `search`: Search across boards, cards, and members


## Error Handling

All tools return JSON dicts. On HTTP errors, the server raises exceptions.

### Common Patterns

- **404 Not Found**: Resource doesn't exist. Check the ID parameter.
- **401 Unauthorized**: Missing or invalid API key. Check `.env` configuration.
- **400 Bad Request**: Invalid parameters. Check required fields and types.
- **429 Too Many Requests**: Rate limited. Wait and retry.
- **500 Server Error**: API-side issue. Retry with backoff.

### No-Content Responses

DELETE operations return `{'status': 'success', 'code': 204}` on success.


## Authentication & Configuration

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `TRELLO_BASE_URL` | API base URL |
| `TRELLO_API_KEY` | API key or token |

### Security Schemes

- `trelloAuth`

### Setup
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Conventions

### Tool Naming
- All tool names are `snake_case`
- Derived from `operationId` in the OpenAPI spec
- Pattern: `{action}{Resource}` (e.g., `listpets`, `getpet`, `createpet`)

### Parameter Naming
- Path params: extracted from URL template (e.g., `petId` → `petid`)
- Query params: passed directly by name
- Request body: always named `body` (dict)

### Enum Parameters

- `filter`: one of 'all', 'closed', 'none', 'open', 'starred', 'unpinned'
- `filter`: one of 'all', 'closed', 'none', 'open'
- `modeltypes`: one of 'actions', 'boards', 'cards', 'members', 'organizations'

### Response Format
- All tools return `dict` (JSON-serializable)
- Successful responses contain the API's response data
- DELETE responses return `{'status': 'success', 'code': 204}`

## Pitfalls

- **Path parameters are required.** Omitting them will cause 404 errors.
- **Request body must be a valid JSON dict.** Pass as the `body` parameter.
- **Enum values must match exactly.** Parameters `filter`, `filter`, `modeltypes` only accept specific values.
- **Rate limits:** Most APIs have rate limits. If you get 429 errors, add delays between calls.
- **Authentication required.** Set the API key in `.env` before using tools.