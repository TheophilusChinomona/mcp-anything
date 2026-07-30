import ast
import json
from pathlib import Path

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.generator import MCPServerGenerator


def _write_spec(tmp_path, spec):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return str(path)


def test_generated_server_is_executable_and_has_runtime(tmp_path, petstore_spec):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    result = MCPServerGenerator(analyzer, server_name="petstore").generate(tmp_path / "out")

    source = Path(result["server_file"]).read_text()
    ast.parse(source)
    assert "if __name__ == \"__main__\":" in source
    assert "mcp.run()" in source
    assert (tmp_path / "out" / "mcp_runtime.py").exists()


def test_generated_server_imports_with_runtime_annotations(tmp_path, petstore_spec, monkeypatch):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    result = MCPServerGenerator(analyzer, server_name="petstore").generate(tmp_path / "out")

    monkeypatch.syspath_prepend(str(tmp_path / "out"))
    import runpy

    runpy.run_path(result["server_file"], run_name="generated_server_test")


def test_default_generation_exposes_read_only_operations_only(tmp_path, petstore_spec):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    result = MCPServerGenerator(analyzer, server_name="petstore").generate(tmp_path / "out")

    inventory = json.loads(Path(result["inventory_file"]).read_text())
    assert {tool["method"] for tool in inventory} <= {"GET", "HEAD", "OPTIONS"}


def test_write_enabled_generation_includes_state_changes(tmp_path, petstore_spec):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    result = MCPServerGenerator(
        analyzer,
        server_name="petstore",
        allow_writes=True,
    ).generate(tmp_path / "out")

    inventory = json.loads(Path(result["inventory_file"]).read_text())
    assert {tool["method"] for tool in inventory} >= {"GET", "POST", "DELETE"}


def test_case_colliding_parameters_compile(tmp_path):
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Collision API", "version": "1"},
        "paths": {
            "/items/{entityKey}": {
                "post": {
                    "operationId": "updateItem",
                    "parameters": [
                        {
                            "name": "entityKey",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "EntityKey",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, spec)).load()
    result = MCPServerGenerator(
        analyzer,
        server_name="collision",
        allow_writes=True,
    ).generate(tmp_path / "out")

    source = Path(result["server_file"]).read_text()
    compile(source, result["server_file"], "exec")


def test_bodyless_tools_do_not_reference_body_name(tmp_path, petstore_spec):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    result = MCPServerGenerator(analyzer, server_name="petstore").generate(tmp_path / "out")
    source = Path(result["server_file"]).read_text()

    # Every generated function without a body parameter must use None.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr == "tool"
            for d in node.decorator_list
        ):
            continue
        names = {arg.arg for arg in node.args.args}
        if "body" not in names:
            assert not any(
                isinstance(n, ast.Name) and n.id == "body" and isinstance(n.ctx, ast.Load)
                for n in ast.walk(node)
            )


def test_generate_profiles_creates_scoped_servers(tmp_path, petstore_spec):
    analyzer = OpenAPIAnalyzer(_write_spec(tmp_path, petstore_spec)).load()
    generator = MCPServerGenerator(analyzer, server_name="petstore")

    result = generator.generate_profiles(
        {
            "read": {"allowed_tags": {"pets"}},
            "write": {"allowed_tags": {"pets"}, "allow_writes": True},
        },
        tmp_path / "profiles",
    )

    assert set(result) == {"read", "write"}
    read_inventory = json.loads(
        Path(result["read"]["inventory_file"]).read_text()
    )
    write_inventory = json.loads(
        Path(result["write"]["inventory_file"]).read_text()
    )
    assert {tool["method"] for tool in read_inventory} <= {"GET", "HEAD", "OPTIONS"}
    assert "POST" in {tool["method"] for tool in write_inventory}
