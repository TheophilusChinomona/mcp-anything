import json
from pathlib import Path

from ops.generate_devpm_profile import (
    BASE_URL,
    CANONICAL_TICKET_FAMILY,
    DENIED_WRITE_OPERATION_IDS,
    DESCRIPTION_OVERRIDES,
    DEVPM_ALLOWED_TAGS,
    ENV_PREFIX,
    SERVER_NAME,
    WRITE_ALLOWED_METHODS,
    WRITE_OPERATION_IDS,
    WRITE_SERVER_NAME,
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


def _write_write_fixture(path: Path) -> None:
    """Write a minimal spec exercising write profile filtering."""
    path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Minimal Dev PM Write", "version": "1.0.0"},
                "paths": {
                    "/api/devpm/DevPmProjects/GetList": {
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
                    "/api/devpm/DevPmTickets/Create": {
                        "post": {
                            "operationId": "post_api_devpm_DevPmTickets_Create",
                            "tags": ["DevPmTickets"],
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                    "/api/devpm/DevPmTickets/Delete": {
                        "delete": {
                            "operationId": "delete_api_devpm_DevPmTickets_Delete",
                            "tags": ["DevPmTickets"],
                            "responses": {"200": {"description": "deleted"}},
                        }
                    },
                    "/api/devpm/DevPmTickets/GetSubscribed": {
                        "get": {
                            "operationId": "get_api_devpm_DevPmTickets_GetSubscribed",
                            "tags": ["DevPmTickets"],
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


def test_devpm_read_profile_default(tmp_path):
    """Verify default profile produces read profile."""
    spec = tmp_path / "minimal-openapi.json"
    output = tmp_path / "profile"
    _write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output)])

    assert result["server_name"] == SERVER_NAME
    assert result["tool_count"] == 1


def test_devpm_write_profile_generates_scoped_writes(tmp_path):
    """Verify write profile generates tools with correct server name, methods, and exclusions."""
    spec = tmp_path / "write-spec.json"
    output = tmp_path / "write-profile"
    _write_write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output), "--profile", "write"])

    # Server identity
    assert result["server_name"] == WRITE_SERVER_NAME
    assert result["env_prefix"] == ENV_PREFIX
    assert result["base_url"] == BASE_URL
    assert Path(result["server_file"]).name == "speccon_crm_devpm_write_server.py"

    # Output files
    assert (output / "tools_inventory.json").exists()
    assert (output / "mcp_runtime.py").exists()
    assert (output / "generation_manifest.json").exists()

    # Should have exactly 2 tools: the GET read operation and the allowed write operation
    assert result["tool_count"] == 3

    inventory = json.loads((output / "tools_inventory.json").read_text())
    op_ids = [tool["operation_id"] for tool in inventory]
    assert "listProjects" in op_ids
    assert "post_api_devpm_DevPmTickets_Create" in op_ids

    # DELETE operation should be excluded
    assert "delete_api_devpm_DevPmTickets_Delete" not in op_ids

    # Non-GET, non-WRITE_OPERATION_IDS operation should be excluded
    assert "createProject" not in op_ids

    # Methods should be GET, POST, PUT, PATCH (no DELETE)
    methods = {tool["method"] for tool in inventory}
    assert methods == {"GET", "POST"}

    # Manifest assertions
    manifest = json.loads((output / "generation_manifest.json").read_text())
    assert manifest["server_name"] == WRITE_SERVER_NAME
    assert manifest["allow_writes"] is True
    assert set(manifest["allowed_methods"]) == {"GET", "POST", "PUT", "PATCH"}
    assert manifest["allowed_tags"] == DEVPM_ALLOWED_TAGS
    assert manifest["endpoint_count"] == 3
    assert manifest["source_endpoint_count"] == 5

    # Server source assertions
    server_source = (output / "speccon_crm_devpm_write_server.py").read_text()
    assert f'FastMCP("{WRITE_SERVER_NAME}")' in server_source
    assert BASE_URL in server_source
    assert "create_project" not in server_source
    assert "delete_api_devpm_DevPmTickets_Delete" not in server_source


def test_devpm_write_profile_cli(tmp_path):
    """Verify --profile write works via CLI."""
    spec = tmp_path / "write-spec.json"
    output = tmp_path / "write-profile"
    _write_write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output), "--profile", "write"])

    assert result["server_name"] == WRITE_SERVER_NAME
    assert result["tool_count"] == 3


def test_devpm_write_profile_excludes_non_ticket_writes(tmp_path):
    """Verify non-Ticket write operations without explicit allowlisting are excluded."""
    spec = tmp_path / "write-spec.json"
    output = tmp_path / "write-profile"
    _write_write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output), "--profile", "write"])

    inventory = json.loads((output / "tools_inventory.json").read_text())
    op_ids = [tool["operation_id"] for tool in inventory]

    # createProject is a DevPmProjects POST not in WRITE_OPERATION_IDS
    assert "createProject" not in op_ids

    # Ticket Delete is denied
    assert "delete_api_devpm_DevPmTickets_Delete" not in op_ids


def test_devpm_write_profile_has_read_operations(tmp_path):
    """Verify GET (read) operations from DevPM-tagged endpoints survive in write profile."""
    spec = tmp_path / "write-spec.json"
    output = tmp_path / "write-profile"
    _write_write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output), "--profile", "write"])

    inventory = json.loads((output / "tools_inventory.json").read_text())
    read_ops = [tool for tool in inventory if tool["method"] == "GET"]

    # The GET listProjects should be included
    assert any(tool["operation_id"] == "listProjects" for tool in read_ops)
    assert len(read_ops) == 2


def test_description_overrides_clarify_user_scoped_semantics():
    """The intent-shaped overrides must cover both route families and key user-scoped reads."""
    # Both families covered for the ambiguous reads
    assert "get_api_devpm_Tickets_GetSubscribed" in DESCRIPTION_OVERRIDES
    assert "get_api_devpm_DevPmTickets_GetSubscribed" in DESCRIPTION_OVERRIDES
    assert "get_api_devpm_Tickets_GetList" in DESCRIPTION_OVERRIDES
    assert "get_api_devpm_DevPmTickets_GetList" in DESCRIPTION_OVERRIDES
    assert "get_api_devpm_Activity_GetUserFeed" in DESCRIPTION_OVERRIDES

    # Subscribed must be explicitly distinguished from assigned
    subscribed = DESCRIPTION_OVERRIDES["get_api_devpm_DevPmTickets_GetSubscribed"].lower()
    assert "not the same as" in subscribed
    assert "assigned" in subscribed
    assert "assigneeuserid" in subscribed
    # GetList override must point at the assigneeuserid filter (the "my tickets" recipe)
    getlist = DESCRIPTION_OVERRIDES["get_api_devpm_DevPmTickets_GetList"].lower()
    assert "assigneeuserid" in getlist
    assert "my tickets" in getlist


def test_description_overrides_are_emitted_in_generated_server(tmp_path):
    """Generated write server embeds the intent-shaped descriptions."""
    spec = tmp_path / "write-spec.json"
    output = tmp_path / "write-profile"
    _write_write_fixture(spec)

    result = main(["--spec", str(spec), "--output", str(output), "--profile", "write"])
    server_source = Path(result["server_file"]).read_text()

    # The subscribed override text must appear in the generated tool docstring
    assert "NOT the same as" in server_source
    assert "follows/watches" in server_source
