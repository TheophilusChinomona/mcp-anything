"""Generate Dev PM MCP profiles from a local OpenAPI spec.

Supports both read-only and ticket-write profiles.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# Allow direct execution as ``python3 ops/generate_devpm_profile.py`` from any
# working directory without making the private spec part of the package.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.generator import MCPServerGenerator


BASE_URL = "https://prod-erp-backend.azurewebsites.net"
SERVER_NAME = "speccon-crm-devpm-read"
ENV_PREFIX = "SPECCON_DEVPM"
DEVPM_ALLOWED_TAGS = [
    "DevPmActivity",
    "DevPmAudit",
    "DevPmBugClaim",
    "DevPmBugTriage",
    "DevPmDashboard",
    "DevPmDocumentImports",
    "DevPmEpics",
    "DevPmEvents",
    "DevPmLabels",
    "DevPmLearners",
    "DevPmMetrics",
    "DevPmNotifications",
    "DevPmPhases",
    "DevPmPoker",
    "DevPmProjectPhases",
    "DevPmProjects",
    "DevPmQuestions",
    "DevPmReleaseNotes",
    "DevPmReports",
    "DevPmSettings",
    "DevPmSprints",
    "DevPmSquads",
    "DevPmSubFeatures",
    "DevPmTeam",
    "DevPmTicketSubtasks",
    "DevPmTickets",
    "DevPmUserPreferences",
]

# Write profile constants
WRITE_SERVER_NAME = "speccon-crm-devpm-write"
WRITE_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH"}

# DevPmTickets + DevPmTicketSubtasks non-DELETE write operations (22)
WRITE_OPERATION_IDS = frozenset({
    "post_api_devpm_DevPmTickets_AddCollaborator",
    "post_api_devpm_DevPmTickets_AddLink",
    "post_api_devpm_DevPmTickets_Approve",
    "post_api_devpm_DevPmTickets_BatchUpdatePlanningStatus",
    "post_api_devpm_DevPmTickets_Create",
    "post_api_devpm_DevPmTickets_CreateComment",
    "post_api_devpm_DevPmTickets_CreateQuestion",
    "post_api_devpm_DevPmTickets_CreateSubtask",
    "post_api_devpm_DevPmTickets_Delegate",
    "post_api_devpm_DevPmTickets_FlagForReview",
    "post_api_devpm_DevPmTickets_Park",
    "post_api_devpm_DevPmTickets_PatchReviewFlag",
    "post_api_devpm_DevPmTickets_QaReject",
    "post_api_devpm_DevPmTickets_RemoveCollaborator",
    "post_api_devpm_DevPmTickets_ResolveQuestion",
    "post_api_devpm_DevPmTickets_Subscribe",
    "post_api_devpm_DevPmTickets_UploadAttachment",
    "post_api_devpm_DevPmTickets_Update",
    "post_api_devpm_DevPmTickets_UpdateSubtask",
    "post_api_devpm_DevPmTicketSubtasks_Complete",
    "post_api_devpm_DevPmTicketSubtasks_Create",
    "put_api_devpm_DevPmTicketSubtasks_Update",
})

# DevPmTickets + DevPmTicketSubtasks DELETE operations (6)
DENIED_WRITE_OPERATION_IDS = frozenset({
    "delete_api_devpm_DevPmTickets_Delete",
    "delete_api_devpm_DevPmTickets_DeleteAttachment",
    "delete_api_devpm_DevPmTickets_DeleteLink",
    "delete_api_devpm_DevPmTickets_DeleteSubtask",
    "delete_api_devpm_DevPmTickets_Unsubscribe",
    "delete_api_devpm_DevPmTicketSubtasks_Delete",
})


def build_profile(spec: Path, output: Path, profile: str = "read") -> dict:
    """Generate a Dev PM profile from ``spec`` into ``output``.

    Args:
        spec: Path to the OpenAPI spec.
        output: Output directory for the generated profile.
        profile: ``"read"`` for read-only profile, ``"write"`` for ticket-write profile.

    Returns:
        dict with generation results.
    """
    if profile == "read":
        return _build_read_profile(spec, output)
    elif profile == "write":
        return _build_write_profile(spec, output)
    else:
        raise ValueError(f"Unknown profile: {profile!r}. Expected 'read' or 'write'.")


def _build_read_profile(spec: Path, output: Path) -> dict:
    """Generate the fixed read-only Dev PM profile."""
    analyzer = OpenAPIAnalyzer(str(spec)).load()
    # Speccon's document does not provide the deployment URL reliably; pin it
    # in the generated artifact rather than inheriting a spec-local value.
    analyzer.base_url = BASE_URL

    generator = MCPServerGenerator(
        analyzer,
        server_name=SERVER_NAME,
        env_prefix=ENV_PREFIX,
        allow_writes=False,
        allowed_methods={"GET"},
        allowed_tags=DEVPM_ALLOWED_TAGS,
    )
    result = generator.generate(str(output))
    result["base_url"] = BASE_URL
    result["env_prefix"] = ENV_PREFIX
    return result


def _build_write_profile(spec: Path, output: Path) -> dict:
    """Generate the ticket-write Dev PM profile."""
    analyzer = OpenAPIAnalyzer(str(spec)).load()
    analyzer.base_url = BASE_URL

    # Get all DevPM-tagged endpoints
    devpm_endpoints = [
        ep
        for ep in analyzer.extract_endpoints()
        if set(ep.tags).intersection(DEVPM_ALLOWED_TAGS)
    ]

    # Collect GET operation IDs from DevPM-tagged endpoints (read operations survive)
    get_ops = {ep.operation_id for ep in devpm_endpoints if ep.method.upper() == "GET"}

    # Union of GET ops and explicit write operation IDs
    allowed_operations = get_ops | WRITE_OPERATION_IDS

    generator = MCPServerGenerator(
        analyzer,
        server_name=WRITE_SERVER_NAME,
        env_prefix=ENV_PREFIX,
        allow_writes=True,
        allowed_methods=WRITE_ALLOWED_METHODS,
        allowed_operations=allowed_operations,
        denied_operations=DENIED_WRITE_OPERATION_IDS,
        allowed_tags=DEVPM_ALLOWED_TAGS,
    )
    result = generator.generate(str(output))
    result["base_url"] = BASE_URL
    result["env_prefix"] = ENV_PREFIX
    return result


def main(argv: Sequence[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="Local OpenAPI JSON/YAML path")
    parser.add_argument("--output", required=True, type=Path, help="Generated profile directory")
    parser.add_argument(
        "--profile",
        choices=["read", "write"],
        default="read",
        help="Profile type to generate (default: read)",
    )
    args = parser.parse_args(argv)

    result = build_profile(args.spec, args.output, args.profile)
    print(f"Generated {result['tool_count']} tools")
    print(f"Server: {result['server_file']}")
    print(f"Manifest: {result['manifest_file']}")
    return result


if __name__ == "__main__":
    main()
