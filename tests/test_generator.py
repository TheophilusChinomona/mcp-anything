"""Tests for MCP server generator."""

import ast
import json
import pytest
from pathlib import Path

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.generator import MCPServerGenerator, _sanitize_name, _schema_to_python_type


class TestSanitizeName:
    """Test the name sanitizer."""

    def test_simple(self):
        assert _sanitize_name("petId") == "petid"

    def test_kebab_case(self):
        assert _sanitize_name("my-operation") == "my_operation"

    def test_dots(self):
        assert _sanitize_name("api.v1.users") == "api_v1_users"

    def test_leading_digit(self):
        assert _sanitize_name("123abc") == "op_123abc"

    def test_spaces(self):
        assert _sanitize_name("my operation") == "my_operation"

    def test_empty(self):
        assert _sanitize_name("") == ""


class TestSchemaToType:
    """Test JSON Schema to Python type conversion."""

    def test_string(self):
        assert _schema_to_python_type({"type": "string"}) == "str"

    def test_integer(self):
        assert _schema_to_python_type({"type": "integer"}) == "int"

    def test_boolean(self):
        assert _schema_to_python_type({"type": "boolean"}) == "bool"

    def test_array(self):
        result = _schema_to_python_type({"type": "array", "items": {"type": "string"}})
        assert result == "list[str]"

    def test_enum(self):
        result = _schema_to_python_type({"type": "string", "enum": ["a", "b", "c"]})
        assert "Literal" in result
        assert "'a'" in result

    def test_empty(self):
        assert _schema_to_python_type({}) == "Any"


class TestMCPServerGenerator:
    """Test the full MCP server generation pipeline."""

    def test_generate_creates_files(self, petstore_spec_file, output_dir):
        """Generator creates all expected output files."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        assert Path(result["server_file"]).exists()
        assert Path(result["config_file"]).exists()
        assert Path(result["inventory_file"]).exists()
        assert Path(result["env_file"]).exists()
        assert Path(result["readme_file"]).exists()

    def test_server_is_valid_python(self, petstore_spec_file, output_dir):
        """Generated server is syntactically valid Python."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        ast.parse(source)  # Raises SyntaxError if invalid

    def test_server_has_all_tools(self, petstore_spec_file, output_dir):
        """Generated server has a @mcp.tool() for each endpoint."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        tool_count = source.count("@mcp.tool()")
        assert tool_count == 5  # 5 endpoints in test spec

    def test_server_has_correct_imports(self, petstore_spec_file, output_dir):
        """Generated server imports required modules."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        assert "from fastmcp import FastMCP" in source
        assert "import httpx" in source
        assert "import os" in source

    def test_server_has_env_config(self, petstore_spec_file, output_dir):
        """Generated server uses environment variables for config."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        assert "TEST_PETS_BASE_URL" in source
        assert "TEST_PETS_API_KEY" in source

    def test_server_has_fastmcp_instance(self, petstore_spec_file, output_dir):
        """Generated server creates a FastMCP instance."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        assert 'FastMCP("test-pets")' in source

    def test_config_json_valid(self, petstore_spec_file, output_dir):
        """Generated mcp_config.json is valid JSON with correct structure."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        config = json.loads(Path(result["config_file"]).read_text())
        assert "mcpServers" in config
        assert "test-pets" in config["mcpServers"]
        server_config = config["mcpServers"]["test-pets"]
        assert "command" in server_config
        assert "args" in server_config
        assert "env" in server_config

    def test_inventory_json_valid(self, petstore_spec_file, output_dir):
        """Generated tools_inventory.json is valid and has all tools."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        inventory = json.loads(Path(result["inventory_file"]).read_text())
        assert len(inventory) == 5
        for tool in inventory:
            assert "name" in tool
            assert "method" in tool
            assert "path" in tool

    def test_tool_count(self, petstore_spec_file, output_dir):
        """Result reports correct tool count."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        assert result["tool_count"] == 5

    def test_custom_env_prefix(self, petstore_spec_file, output_dir):
        """Custom env prefix is used in generated code."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets", env_prefix="MY_API")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_bytes().decode('utf-8')
        assert "MY_API_BASE_URL" in source
        assert "MY_API_API_KEY" in source

    def test_path_params_in_tools(self, petstore_spec_file, output_dir):
        """Path parameters appear in tool function signatures."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        # getPet should have petid param
        assert "def getpet(" in source or "def get_pet(" in source

    def test_request_body_in_post_tools(self, petstore_spec_file, output_dir):
        """POST endpoints with request body get a body parameter."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        # createPet should have body param
        assert "body: dict" in source

    def test_enum_in_tool_signature(self, petstore_spec_file, output_dir):
        """Enum parameters get Literal types in tool signatures."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        
        generator = MCPServerGenerator(analyzer, server_name="test-pets")
        result = generator.generate(output_dir)
        
        source = Path(result["server_file"]).read_text()
        assert "Literal" in source
        assert "'available'" in source
