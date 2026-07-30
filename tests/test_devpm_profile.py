import json
from pathlib import Path

from ops.generate_devpm_profile import (
    BASE_URL,
    DEVPM_ALLOWED_TAGS,
    ENV_PREFIX,
    SERVER_NAME,
    main,
)


def _write_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Minimal Dev PM", "version": "1.0.0"},
                "paths": {
                    "/projects": {
                        "get": {
                            "operationId": "listProjects",
                            "tags": ["DevPmProjects"],
                            "responses": {"200": {"description": "ok"}},
                        },
                        "post": {
                            "operationId": "createProject",
                            "tags": ["DevPmProjects"],
                            "responses": {"201": {"description": "created"}},
                        },
                    },
                    "/other": {
                        "get": {
                            "operationId": "listOther",
                            "tags": ["Other"],
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                },
            }
        )
    )


def test_devpm_profile_cli_generates_fixed_read_only_profile(tmp_path):
    spec = tmp_path / "minimal-openapi.json"
    output = tmp_path / "profile"
    _write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output)])

    assert result["tool_count"] == 1
    assert result["server_name"] == SERVER_NAME
    assert result["env_prefix"] == ENV_PREFIX
    assert result["base_url"] == BASE_URL
    assert Path(result["server_file"]).name == "speccon_crm_devpm_read_server.py"
    assert (output / "tools_inventory.json").exists()
    assert (output / "mcp_runtime.py").exists()
    assert (output / "generation_manifest.json").exists()

    inventory = json.loads((output / "tools_inventory.json").read_text())
    assert [tool["operation_id"] for tool in inventory] == ["listProjects"]
    assert inventory[0]["method"] == "GET"

    manifest = json.loads((output / "generation_manifest.json").read_text())
    assert manifest["server_name"] == SERVER_NAME
    assert manifest["env_prefix"] == ENV_PREFIX
    assert manifest["allow_writes"] is False
    assert manifest["allowed_tags"] == DEVPM_ALLOWED_TAGS
    assert manifest["endpoint_count"] == 1
    assert manifest["source_endpoint_count"] == 3

    server_source = (output / "speccon_crm_devpm_read_server.py").read_text()
    assert f'FastMCP("{SERVER_NAME}")' in server_source
    assert f'{ENV_PREFIX}_BASE_URL' in server_source
    assert BASE_URL in server_source
    assert "create_project" not in server_source
    assert "list_other" not in server_source


def test_devpm_tag_allowlist_is_exact():
    assert DEVPM_ALLOWED_TAGS == [
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


def test_devpm_profile_handles_recursive_openapi_schema(tmp_path):
    spec = tmp_path / "recursive-openapi.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Recursive Dev PM", "version": "1.0.0"},
                "paths": {
                    "/projects": {
                        "get": {
                            "operationId": "listProjects",
                            "tags": ["DevPmProjects"],
                            "responses": {
                                "200": {
                                    "description": "ok",
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/Node"}
                                        }
                                    },
                                }
                            },
                        }
                    }
                },
                "components": {
                    "schemas": {
                        "Node": {
                            "type": "object",
                            "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                        }
                    }
                },
            }
        )
    )

    result = main(["--spec", str(spec), "--output", str(tmp_path / "profile")])

    assert result["tool_count"] == 1
