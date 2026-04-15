"""
Skill Generator — produces agent-facing SKILL.md files alongside MCP servers.

When MCP-Anything generates an MCP server, it also generates a SKILL.md
that tells AI agents HOW to use the tools effectively. This is the agent's
"user manual" for the generated MCP server.

Inspired by CLI-Anything's SKILL.md generation (Phase 6.5).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from mcp_anything.analyzer import EndpointInfo, OpenAPIAnalyzer


def _sanitize_name(name: str) -> str:
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    if name and name[0].isdigit():
        name = f"op_{name}"
    return name.lower()


class SkillGenerator:
    """Generate agent-facing SKILL.md from an OpenAPI spec."""

    def __init__(self, analyzer: OpenAPIAnalyzer, server_name: str = ""):
        self.analyzer = analyzer
        self.server_name = server_name or self._derive_name()

    def _derive_name(self) -> str:
        summary = self.analyzer.summary()
        title = summary.get("title", "api")
        return re.sub(r'[^a-zA-Z0-9_-]', '-', title.lower()).strip('-') or "api"

    def generate(self, endpoints: list[EndpointInfo], output_path: Path) -> Path:
        """Generate SKILL.md and write it to output_path."""
        summary = self.analyzer.summary()
        skill_content = self._build_skill_md(summary, endpoints)
        skill_file = output_path / "SKILL.md"
        skill_file.write_text(skill_content)
        return skill_file

    def _build_skill_md(self, summary: dict, endpoints: list[EndpointInfo]) -> str:
        sections = []

        # ── Header ──
        sections.append(self._header(summary))

        # ── Overview ──
        sections.append(self._overview(summary, endpoints))

        # ── Tools Reference ──
        sections.append(self._tools_reference(endpoints))

        # ── Workflows ──
        sections.append(self._workflows(endpoints))

        # ── Error Handling ──
        sections.append(self._error_handling(endpoints))

        # ── Auth & Config ──
        sections.append(self._auth_config(summary))

        # ── Conventions ──
        sections.append(self._conventions(endpoints))

        # ── Pitfalls ──
        sections.append(self._pitfalls(endpoints, summary))

        return "\n\n".join(sections)

    def _header(self, summary: dict) -> str:
        name = self.server_name
        title = summary.get("title", "API")
        return f"""---
name: {name}
description: Agent skill for using the {title} MCP tools. Covers all {summary.get('endpoint_count', 0)} endpoints with workflows, error handling, and conventions.
version: 1.0.0
author: mcp-anything
metadata:
  hermes:
    tags: [mcp, api, {name}]
    source: openapi-spec
---

# {title} — Agent Skill

This skill defines how to use the **{name}** MCP tools effectively."""

    def _overview(self, summary: dict, endpoints: list[EndpointInfo]) -> str:
        # Group by tags
        tag_groups = defaultdict(list)
        for ep in endpoints:
            for tag in (ep.tags or ["other"]):
                tag_groups[tag].append(ep)

        lines = ["## Overview", ""]
        lines.append(f"**API:** {summary.get('title', 'Unknown')} v{summary.get('version', '?')}")
        lines.append(f"**Base URL:** `{summary.get('base_url', 'N/A')}`")
        lines.append(f"**Total Tools:** {len(endpoints)}")
        lines.append("")

        lines.append("### Tool Groups")
        lines.append("")
        for tag, eps in sorted(tag_groups.items()):
            names = ", ".join(f"`{_sanitize_name(ep.operation_id)}`" for ep in eps)
            lines.append(f"- **{tag}** ({len(eps)} tools): {names}")

        return "\n".join(lines)

    def _tools_reference(self, endpoints: list[EndpointInfo]) -> str:
        lines = ["## Tools Reference", ""]
        lines.append("Use these tools to interact with the API. Each tool maps to an API endpoint.")
        lines.append("")

        for ep in endpoints:
            func_name = _sanitize_name(ep.operation_id)
            method = ep.method
            path = ep.path
            summary_text = ep.summary or ep.description or f"{method} {path}"

            lines.append(f"### `{func_name}`")
            lines.append(f"**{method}** `{path}`")
            lines.append("")
            lines.append(summary_text)
            lines.append("")

            # Parameters
            if ep.parameters:
                lines.append("**Parameters:**")
                for p in ep.parameters:
                    req = "required" if p.required else "optional"
                    ptype = p.schema.get("type", "any")
                    desc = p.description or p.name
                    enum_hint = ""
                    if "enum" in p.schema:
                        enum_hint = f" — one of: {', '.join(repr(v) for v in p.schema['enum'])}"
                    default_hint = ""
                    if "default" in p.schema:
                        default_hint = f" (default: {p.schema['default']})"
                    lines.append(f"- `{_sanitize_name(p.name)}` ({ptype}, {p.location}, {req}): {desc}{enum_hint}{default_hint}")
                lines.append("")

            # Request body
            if ep.request_body:
                lines.append("**Request Body:** JSON object (pass as `body` parameter)")
                lines.append("")

        return "\n".join(lines)

    def _workflows(self, endpoints: list[EndpointInfo]) -> str:
        """Detect common API patterns and document workflows."""
        lines = ["## Common Workflows", ""]

        # Detect CRUD patterns
        crud_groups = self._detect_crud(endpoints)
        if crud_groups:
            lines.append("### CRUD Operations")
            lines.append("")
            for resource, ops in crud_groups.items():
                lines.append(f"**{resource}:**")
                if "list" in ops:
                    lines.append(f"1. `{ops['list']}` — List all {resource}")
                if "get" in ops:
                    lines.append(f"2. `{ops['get']}` — Get a specific {resource} by ID")
                if "create" in ops:
                    lines.append(f"3. `{ops['create']}` — Create a new {resource}")
                if "update" in ops:
                    lines.append(f"4. `{ops['update']}` — Update an existing {resource}")
                if "delete" in ops:
                    lines.append(f"5. `{ops['delete']}` — Delete a {resource}")
                lines.append("")

        # Detect search/filter patterns
        search_tools = [
            ep for ep in endpoints
            if any(kw in ep.operation_id.lower() for kw in ("search", "find", "filter", "query"))
        ]
        if search_tools:
            lines.append("### Search & Filter")
            lines.append("")
            for ep in search_tools:
                func_name = _sanitize_name(ep.operation_id)
                lines.append(f"- `{func_name}`: {ep.summary or ep.description or 'Search endpoint'}")
            lines.append("")

        # Detect auth/user patterns
        auth_tools = [
            ep for ep in endpoints
            if any(kw in ep.operation_id.lower() for kw in ("login", "logout", "auth", "token", "session"))
        ]
        if auth_tools:
            lines.append("### Authentication")
            lines.append("")
            for ep in auth_tools:
                func_name = _sanitize_name(ep.operation_id)
                lines.append(f"- `{func_name}`: {ep.summary or 'Auth endpoint'}")
            lines.append("")
            lines.append("**Tip:** Call auth endpoints first if the API requires session tokens.")
            lines.append("")

        if not crud_groups and not search_tools and not auth_tools:
            lines.append("No standard patterns detected. See Tools Reference above for available operations.")

        return "\n".join(lines)

    def _detect_crud(self, endpoints: list[EndpointInfo]) -> dict:
        """Detect CRUD patterns by matching operation IDs and HTTP methods."""
        # Group endpoints by path prefix (resource name)
        resources = defaultdict(dict)

        for ep in endpoints:
            func_lower = ep.operation_id.lower()
            path_parts = [p for p in ep.path.strip("/").split("/") if not p.startswith("{")]

            # Try to identify the resource name
            resource = None
            if path_parts:
                resource = path_parts[-1] if not path_parts[-1].startswith("{") else (path_parts[0] if path_parts else None)

            if not resource:
                continue

            # Classify the operation
            if ep.method == "GET" and "{" not in ep.path:
                resources[resource]["list"] = _sanitize_name(ep.operation_id)
            elif ep.method == "GET" and "{" in ep.path:
                resources[resource]["get"] = _sanitize_name(ep.operation_id)
            elif ep.method == "POST":
                resources[resource]["create"] = _sanitize_name(ep.operation_id)
            elif ep.method in ("PUT", "PATCH"):
                resources[resource]["update"] = _sanitize_name(ep.operation_id)
            elif ep.method == "DELETE":
                resources[resource]["delete"] = _sanitize_name(ep.operation_id)

            # Also check operation ID keywords
            if "list" in func_lower or "getall" in func_lower:
                resources[resource]["list"] = _sanitize_name(ep.operation_id)
            elif "getbyid" in func_lower or "getby" in func_lower:
                resources[resource]["get"] = _sanitize_name(ep.operation_id)
            elif "create" in func_lower or "add" in func_lower:
                resources[resource]["create"] = _sanitize_name(ep.operation_id)
            elif "update" in func_lower or "edit" in func_lower:
                resources[resource]["update"] = _sanitize_name(ep.operation_id)
            elif "delete" in func_lower or "remove" in func_lower:
                resources[resource]["delete"] = _sanitize_name(ep.operation_id)

        # Only return resources with at least 2 operations
        return {k: v for k, v in resources.items() if len(v) >= 2}

    def _error_handling(self, endpoints: list[EndpointInfo]) -> str:
        lines = ["## Error Handling", ""]
        lines.append("All tools return JSON dicts. On HTTP errors, the server raises exceptions.")
        lines.append("")
        lines.append("### Common Patterns")
        lines.append("")
        lines.append("- **404 Not Found**: Resource doesn't exist. Check the ID parameter.")
        lines.append("- **401 Unauthorized**: Missing or invalid API key. Check `.env` configuration.")
        lines.append("- **400 Bad Request**: Invalid parameters. Check required fields and types.")
        lines.append("- **429 Too Many Requests**: Rate limited. Wait and retry.")
        lines.append("- **500 Server Error**: API-side issue. Retry with backoff.")
        lines.append("")

        # Check for delete operations that return 204
        no_content = [ep for ep in endpoints if ep.method == "DELETE"]
        if no_content:
            lines.append("### No-Content Responses")
            lines.append("")
            lines.append("DELETE operations return `{'status': 'success', 'code': 204}` on success.")
            lines.append("")

        return "\n".join(lines)

    def _auth_config(self, summary: dict) -> str:
        lines = ["## Authentication & Configuration", ""]
        env_prefix = self.server_name.upper().replace("-", "_").replace(" ", "_")

        lines.append("### Environment Variables")
        lines.append("")
        lines.append(f"| Variable | Purpose |")
        lines.append(f"|----------|---------|")
        lines.append(f"| `{env_prefix}_BASE_URL` | API base URL |")
        lines.append(f"| `{env_prefix}_API_KEY` | API key or token |")
        lines.append("")

        security = summary.get("security_schemes", [])
        if security:
            lines.append("### Security Schemes")
            lines.append("")
            for scheme in security:
                lines.append(f"- `{scheme}`")
            lines.append("")

        lines.append("### Setup")
        lines.append("```bash")
        lines.append("cp .env.example .env")
        lines.append("# Edit .env with your credentials")
        lines.append("```")

        return "\n".join(lines)

    def _conventions(self, endpoints: list[EndpointInfo]) -> str:
        lines = ["## Conventions", ""]
        lines.append("### Tool Naming")
        lines.append("- All tool names are `snake_case`")
        lines.append("- Derived from `operationId` in the OpenAPI spec")
        lines.append("- Pattern: `{action}{Resource}` (e.g., `listpets`, `getpet`, `createpet`)")
        lines.append("")

        lines.append("### Parameter Naming")
        lines.append("- Path params: extracted from URL template (e.g., `petId` → `petid`)")
        lines.append("- Query params: passed directly by name")
        lines.append("- Request body: always named `body` (dict)")
        lines.append("")

        # Check for enum params
        enum_params = []
        for ep in endpoints:
            for p in ep.parameters:
                if "enum" in p.schema:
                    enum_params.append((p.name, p.schema["enum"]))

        if enum_params:
            lines.append("### Enum Parameters")
            lines.append("")
            for name, values in enum_params[:5]:
                vals = ", ".join(repr(v) for v in values)
                lines.append(f"- `{_sanitize_name(name)}`: one of {vals}")
            if len(enum_params) > 5:
                lines.append(f"- ... and {len(enum_params) - 5} more")
            lines.append("")

        lines.append("### Response Format")
        lines.append("- All tools return `dict` (JSON-serializable)")
        lines.append("- Successful responses contain the API's response data")
        lines.append("- DELETE responses return `{'status': 'success', 'code': 204}`")

        return "\n".join(lines)

    def _pitfalls(self, endpoints: list[EndpointInfo], summary: dict) -> str:
        lines = ["## Pitfalls", ""]

        # Check for path params
        path_params = set()
        for ep in endpoints:
            for p in ep.parameters:
                if p.location == "path":
                    path_params.add(p.name)

        if path_params:
            lines.append("- **Path parameters are required.** Omitting them will cause 404 errors.")

        # Check for POST/PUT with body
        body_endpoints = [ep for ep in endpoints if ep.request_body]
        if body_endpoints:
            lines.append("- **Request body must be a valid JSON dict.** Pass as the `body` parameter.")

        # Check for pagination
        pagination = [
            ep for ep in endpoints
            if any(p.name.lower() in ("limit", "offset", "page", "per_page", "cursor")
                   for p in ep.parameters)
        ]
        if pagination:
            lines.append("- **Pagination:** List endpoints may return partial results. Check for `limit`/`offset`/`page` params.")

        # Check for enums
        enum_params = [
            p for ep in endpoints for p in ep.parameters
            if "enum" in p.schema
        ]
        if enum_params:
            names = ", ".join(f"`{_sanitize_name(p.name)}`" for p in enum_params[:3])
            lines.append(f"- **Enum values must match exactly.** Parameters {names} only accept specific values.")

        # Rate limiting
        lines.append("- **Rate limits:** Most APIs have rate limits. If you get 429 errors, add delays between calls.")

        # Auth
        security = summary.get("security_schemes", [])
        if security:
            lines.append("- **Authentication required.** Set the API key in `.env` before using tools.")

        return "\n".join(lines)
