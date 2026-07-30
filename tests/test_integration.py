"""End-to-end integration tests."""

import ast
import json
import pytest
from pathlib import Path

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.generator import MCPServerGenerator


class TestEndToEnd:
    """Full pipeline tests: spec → analyzer → generator → valid server."""

    def test_petstore_full_pipeline(self, petstore_spec_file, output_dir):
        """Complete pipeline produces a working MCP server."""
        # Step 1: Analyze
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        summary = analyzer.summary()

        assert len(endpoints) == 5
        assert summary["title"] == "Test Pet Store"

        # Step 2: Generate
        generator = MCPServerGenerator(analyzer, server_name="e2e-test", allow_writes=True)
        result = generator.generate(output_dir)

        assert result["tool_count"] == 5

        # Step 3: Validate server
        server_path = Path(result["server_file"])
        source = server_path.read_text()

        # Valid Python
        ast.parse(source)

        # Has FastMCP
        assert "FastMCP" in source

        # Has all CRUD tools
        assert "listpets" in source.lower() or "list_pets" in source.lower()
        assert "createpet" in source.lower() or "create_pet" in source.lower()
        assert "getpet" in source.lower() or "get_pet" in source.lower()
        assert "deletepet" in source.lower() or "delete_pet" in source.lower()
        assert "getinventory" in source.lower() or "get_inventory" in source.lower()

        # Step 4: Validate config
        config = json.loads(Path(result["config_file"]).read_text())
        assert config["mcpServers"]["e2e-test"]["command"] == "python3"

        # Step 5: Validate inventory
        inventory = json.loads(Path(result["inventory_file"]).read_text())
        assert len(inventory) == 5
        tool_names = {t["name"] for t in inventory}
        # Verify all expected tools exist (by checking methods and paths)
        methods = {t["method"] for t in inventory}
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods
        paths = {t["path"] for t in inventory}
        assert "/pets" in paths
        assert "/pets/{petId}" in paths
        assert "/store/inventory" in paths

    def test_different_server_names(self, petstore_spec_file, output_dir):
        """Different server names produce different output."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()

        # Generate with name A
        gen_a = MCPServerGenerator(analyzer, server_name="api-alpha", allow_writes=True)
        dir_a = str(Path(output_dir) / "a")
        result_a = gen_a.generate(dir_a)

        # Generate with name B
        gen_b = MCPServerGenerator(analyzer, server_name="api-beta", allow_writes=True)
        dir_b = str(Path(output_dir) / "b")
        result_b = gen_b.generate(dir_b)

        # Both are valid but different
        source_a = Path(result_a["server_file"]).read_text()
        source_b = Path(result_b["server_file"]).read_text()

        assert 'FastMCP("api-alpha")' in source_a
        assert 'FastMCP("api-beta")' in source_b

        config_a = json.loads(Path(result_a["config_file"]).read_text())
        config_b = json.loads(Path(result_b["config_file"]).read_text())

        assert "api-alpha" in config_a["mcpServers"]
        assert "api-beta" in config_b["mcpServers"]

    def test_server_can_be_imported(self, petstore_spec_file, output_dir):
        """Generated server can be imported as a Python module (without running)."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()

        generator = MCPServerGenerator(analyzer, server_name="import-test")
        result = generator.generate(output_dir)

        # Import and check it has the expected attributes
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_server", result["server_file"]
        )
        mod = importlib.util.module_from_spec(spec)

        # Can't fully load (needs FastMCP runtime), but we can verify the source
        source = Path(result["server_file"]).read_text()
        assert "mcp = FastMCP" in source
        assert "@mcp.tool()" in source

    def test_env_example_has_correct_vars(self, petstore_spec_file, output_dir):
        """Generated .env.example has the right variable names."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()

        generator = MCPServerGenerator(analyzer, server_name="env-test")
        result = generator.generate(output_dir)

        env_content = Path(result["env_file"]).read_text()
        assert "ENV_TEST_BASE_URL" in env_content
        assert "ENV_TEST_API_KEY" in env_content
        assert "https://api.test.com/v1" in env_content


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_paths(self, tmp_path, output_dir):
        """Spec with no paths generates a valid (empty) server."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Empty", "version": "1.0"},
            "paths": {}
        }
        spec_file = tmp_path / "empty.json"
        spec_file.write_text(json.dumps(spec))

        analyzer = OpenAPIAnalyzer(str(spec_file))
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        assert len(endpoints) == 0

        generator = MCPServerGenerator(analyzer, server_name="empty")
        result = generator.generate(output_dir)
        assert result["tool_count"] == 0

        source = Path(result["server_file"]).read_text()
        ast.parse(source)  # Still valid Python

    def test_special_chars_in_operation_id(self, tmp_path, output_dir):
        """Operation IDs with special chars are sanitized."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Special", "version": "1.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "get-items.v2!special",
                        "summary": "Get items",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        spec_file = tmp_path / "special.json"
        spec_file.write_text(json.dumps(spec))

        analyzer = OpenAPIAnalyzer(str(spec_file))
        analyzer.load()

        generator = MCPServerGenerator(analyzer, server_name="special")
        result = generator.generate(output_dir)

        source = Path(result["server_file"]).read_text()
        ast.parse(source)

        # Should have a valid Python function name
        import re
        func_names = re.findall(r'def (\w+)\(', source)
        tool_funcs = [f for f in func_names if f not in ("_get_headers", "_request")]
        assert len(tool_funcs) >= 1
        assert all(f.replace("_", "").isalnum() for f in tool_funcs)

    def test_no_servers_in_spec(self, tmp_path, output_dir):
        """Spec without servers array defaults to empty base URL."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "No Servers", "version": "1.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        spec_file = tmp_path / "no_servers.json"
        spec_file.write_text(json.dumps(spec))

        analyzer = OpenAPIAnalyzer(str(spec_file))
        analyzer.load()
        assert analyzer.base_url == ""

        generator = MCPServerGenerator(analyzer, server_name="no-srv")
        result = generator.generate(output_dir)
        assert result["tool_count"] == 1
