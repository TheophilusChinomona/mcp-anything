"""Generate the read-only Dev PM MCP profile from a local OpenAPI spec."""

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


def build_profile(spec: Path, output: Path) -> dict:
    """Generate the fixed Dev PM profile from ``spec`` into ``output``."""
    analyzer = OpenAPIAnalyzer(str(spec)).load()
    # Speccon's document does not provide the deployment URL reliably; pin it
    # in the generated artifact rather than inheriting a spec-local value.
    analyzer.base_url = BASE_URL

    generator = MCPServerGenerator(
        analyzer,
        server_name=SERVER_NAME,
        env_prefix=ENV_PREFIX,
        allow_writes=False,
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
    args = parser.parse_args(argv)

    result = build_profile(args.spec, args.output)
    print(f"Generated {result['tool_count']} tools")
    print(f"Server: {result['server_file']}")
    print(f"Manifest: {result['manifest_file']}")
    return result


if __name__ == "__main__":
    main()
