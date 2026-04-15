"""Shared test fixtures for MCP-Anything tests."""

import json
import pytest
from pathlib import Path


# ─── Minimal OpenAPI 3.0 Spec for testing ────────────────────────────────────

PETSTORE_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Test Pet Store",
        "version": "1.0.0",
        "description": "A test pet store API"
    },
    "servers": [{"url": "https://api.test.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "description": "Returns a list of pets with optional filtering",
                "tags": ["pets"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 20}
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "enum": ["available", "pending", "sold"]}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Pet"}
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "tags": ["pets"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NewPet"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Created pet",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        }
                    }
                }
            }
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "tags": ["pets"],
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "A pet",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        }
                    }
                }
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "tags": ["pets"],
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "204": {"description": "Pet deleted"}
                }
            }
        },
        "/store/inventory": {
            "get": {
                "operationId": "getInventory",
                "summary": "Returns pet inventories by status",
                "tags": ["store"],
                "responses": {
                    "200": {
                        "description": "Inventory map",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {"type": "integer"}
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "pending", "sold"]}
                },
                "required": ["id", "name"]
            },
            "NewPet": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "securitySchemes": {
            "api_key": {
                "type": "apiKey",
                "name": "X-API-Key",
                "in": "header"
            }
        }
    }
}


@pytest.fixture
def petstore_spec():
    """Return the test Petstore spec as a dict."""
    return PETSTORE_SPEC


@pytest.fixture
def petstore_spec_file(tmp_path):
    """Write the test spec to a temp file and return the path."""
    spec_file = tmp_path / "petstore.json"
    spec_file.write_text(json.dumps(PETSTORE_SPEC, indent=2))
    return str(spec_file)


@pytest.fixture
def output_dir(tmp_path):
    """Return a temp output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return str(d)
