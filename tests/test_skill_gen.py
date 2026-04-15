"""Tests for agent-facing SKILL.md generator."""

import pytest
from pathlib import Path

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.skill_gen import SkillGenerator


class TestSkillGenerator:
    """Test SKILL.md generation for agents."""

    def test_skill_file_created(self, petstore_spec_file, output_dir):
        """SKILL.md is created alongside other output files."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))

        assert skill_file.exists()
        assert skill_file.name == "SKILL.md"

    def test_skill_has_frontmatter(self, petstore_spec_file, output_dir):
        """SKILL.md has YAML frontmatter with name and description."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert content.startswith("---")
        assert "name: test-api" in content
        assert "description:" in content

    def test_skill_has_tools_reference(self, petstore_spec_file, output_dir):
        """SKILL.md documents all tools."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "## Tools Reference" in content
        assert "listpets" in content
        assert "createpet" in content
        assert "getpet" in content
        assert "deletepet" in content
        assert "getinventory" in content

    def test_skill_has_workflows(self, petstore_spec_file, output_dir):
        """SKILL.md detects and documents CRUD workflows."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "## Common Workflows" in content
        assert "CRUD" in content or "crud" in content.lower()

    def test_skill_has_error_handling(self, petstore_spec_file, output_dir):
        """SKILL.md documents error handling patterns."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "## Error Handling" in content
        assert "404" in content
        assert "401" in content

    def test_skill_has_pitfalls(self, petstore_spec_file, output_dir):
        """SKILL.md documents common pitfalls."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "## Pitfalls" in content
        assert "Path parameters are required" in content

    def test_skill_has_enum_docs(self, petstore_spec_file, output_dir):
        """SKILL.md documents enum parameters."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "'available'" in content
        assert "'pending'" in content
        assert "'sold'" in content

    def test_skill_has_auth_section(self, petstore_spec_file, output_dir):
        """SKILL.md documents authentication."""
        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()

        gen = SkillGenerator(analyzer, server_name="test-api")
        skill_file = gen.generate(endpoints, Path(output_dir))
        content = skill_file.read_text()

        assert "## Authentication" in content or "## Authentication & Configuration" in content
        assert "TEST_API_BASE_URL" in content
        assert "TEST_API_API_KEY" in content

    def test_skill_generated_in_pipeline(self, petstore_spec_file, output_dir):
        """SKILL.md is generated as part of the MCPServerGenerator pipeline."""
        from mcp_anything.generator import MCPServerGenerator

        analyzer = OpenAPIAnalyzer(petstore_spec_file)
        analyzer.load()

        generator = MCPServerGenerator(analyzer, server_name="pipeline-test")
        result = generator.generate(output_dir)

        assert "skill_file" in result
        assert Path(result["skill_file"]).exists()

        content = Path(result["skill_file"]).read_text()
        assert "name: pipeline-test" in content
