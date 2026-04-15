"""Tests for OpenAPI spec analyzer."""

import json
import pytest
from mcp_anything.analyzer import OpenAPIAnalyzer, EndpointInfo, ParameterInfo


class TestOpenAPIAnalyzer:
    """Test the OpenAPI spec parser."""

    def test_load_from_file(self, petstore_spec_file):
        """Can load a spec from a local JSON file."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        assert analyzer.spec is not None
        assert analyzer.spec["info"]["title"] == "Test Pet Store"

    def test_load_from_dict_string(self, petstore_spec, tmp_path):
        """Can load from a raw JSON string."""
        spec_str = json.dumps(petstore_spec)
        analyzer = OpenAPIAnalyzer(spec_str)
        analyzer.load()
        assert analyzer.spec["info"]["title"] == "Test Pet Store"

    def test_base_url_extraction(self, petstore_spec_file):
        """Extracts base URL from servers array."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        assert analyzer.base_url == "https://api.test.com/v1"

    def test_extract_endpoints(self, petstore_spec_file):
        """Extracts all endpoints from the spec."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        assert len(endpoints) == 5  # listPets, createPet, getPet, deletePet, getInventory

    def test_endpoint_methods(self, petstore_spec_file):
        """Endpoint methods are correctly identified."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        methods = {ep.operation_id: ep.method for ep in endpoints}
        assert methods["listPets"] == "GET"
        assert methods["createPet"] == "POST"
        assert methods["getPet"] == "GET"
        assert methods["deletePet"] == "DELETE"

    def test_endpoint_paths(self, petstore_spec_file):
        """Endpoint paths are correctly extracted."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        paths = {ep.operation_id: ep.path for ep in endpoints}
        assert paths["listPets"] == "/pets"
        assert paths["getPet"] == "/pets/{petId}"
        assert paths["getInventory"] == "/store/inventory"

    def test_query_parameters(self, petstore_spec_file):
        """Query parameters are extracted with schema info."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        list_pets = next(ep for ep in endpoints if ep.operation_id == "listPets")
        
        query_params = [p for p in list_pets.parameters if p.location == "query"]
        assert len(query_params) == 2
        
        limit_param = next(p for p in query_params if p.name == "limit")
        assert limit_param.required is False
        assert limit_param.schema["type"] == "integer"
        assert limit_param.schema["default"] == 20

    def test_path_parameters(self, petstore_spec_file):
        """Path parameters are always required."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        get_pet = next(ep for ep in endpoints if ep.operation_id == "getPet")
        
        path_params = [p for p in get_pet.parameters if p.location == "path"]
        assert len(path_params) == 1
        assert path_params[0].name == "petId"
        assert path_params[0].required is True
        assert path_params[0].schema["type"] == "integer"

    def test_enum_parameters(self, petstore_spec_file):
        """Enum values in parameters are preserved."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        list_pets = next(ep for ep in endpoints if ep.operation_id == "listPets")
        
        status_param = next(p for p in list_pets.parameters if p.name == "status")
        assert "enum" in status_param.schema
        assert status_param.schema["enum"] == ["available", "pending", "sold"]

    def test_request_body(self, petstore_spec_file):
        """Request body is extracted for POST endpoints."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        create_pet = next(ep for ep in endpoints if ep.operation_id == "createPet")
        
        assert create_pet.request_body is not None
        assert create_pet.request_body["content_type"] == "application/json"
        assert "schema" in create_pet.request_body

    def test_response_schema(self, petstore_spec_file):
        """Response schema is extracted for 200 responses."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        list_pets = next(ep for ep in endpoints if ep.operation_id == "listPets")
        
        assert list_pets.response_schema is not None

    def test_tags(self, petstore_spec_file):
        """Tags are extracted from endpoints."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        list_pets = next(ep for ep in endpoints if ep.operation_id == "listPets")
        get_inv = next(ep for ep in endpoints if ep.operation_id == "getInventory")
        
        assert "pets" in list_pets.tags
        assert "store" in get_inv.tags

    def test_summary(self, petstore_spec_file):
        """Summary returns correct metadata."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        analyzer.extract_endpoints()
        summary = analyzer.summary()
        
        assert summary["title"] == "Test Pet Store"
        assert summary["version"] == "1.0.0"
        assert summary["base_url"] == "https://api.test.com/v1"
        assert summary["endpoint_count"] == 5
        assert "api_key" in summary["security_schemes"]
        assert set(summary["tags"]) == {"pets", "store"}

    def test_no_operation_id_generates_one(self, tmp_path):
        """Endpoints without operationId get a generated one."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/items/{itemId}": {
                    "get": {
                        "summary": "Get item",
                        "parameters": [{"name": "itemId", "in": "path", "required": True, "schema": {"type": "string"}}],
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        spec_file = tmp_path / "no_op_id.json"
        spec_file.write_text(json.dumps(spec))
        
        analyzer = OpenAPIAnalyzer(str(spec_file))
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        
        assert len(endpoints) == 1
        assert endpoints[0].operation_id  # Should have a generated ID
        assert "get" in endpoints[0].operation_id.lower() or "items" in endpoints[0].operation_id.lower()
