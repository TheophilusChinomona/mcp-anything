"""OpenAPI spec analyzer - extracts MCP tool definitions from API specs."""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

import yaml
import httpx
import jsonref


@dataclass
class ParameterInfo:
    """An extracted parameter from an endpoint."""
    name: str
    location: str  # query, path, header, cookie
    required: bool = False
    schema: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class EndpointInfo:
    """An extracted endpoint ready for MCP tool generation."""
    operation_id: str
    method: str
    path: str
    summary: str
    description: str
    tags: list[str]
    parameters: list[ParameterInfo]
    request_body: Optional[dict]
    response_schema: Optional[dict]
    security: list[dict]


class OpenAPIAnalyzer:
    """Parse an OpenAPI 3.x spec and extract tool-ready endpoint definitions."""

    def __init__(self, spec_source: str):
        """
        Args:
            spec_source: URL to a spec, local file path, or raw JSON/YAML string.
        """
        self.spec_source = spec_source
        self.spec: dict = {}
        self.base_url: str = ""
        self.endpoints: list[EndpointInfo] = []

    def load(self) -> "OpenAPIAnalyzer":
        """Load and resolve the OpenAPI spec."""
        if self.spec_source.startswith(("http://", "https://")):
            resp = httpx.get(self.spec_source, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "yaml" in content_type or self.spec_source.endswith((".yaml", ".yml")):
                self.spec = yaml.safe_load(resp.text)
            else:
                self.spec = resp.json()
        elif Path(self.spec_source).exists():
            text = Path(self.spec_source).read_text()
            if self.spec_source.endswith((".yaml", ".yml")):
                self.spec = yaml.safe_load(text)
            else:
                self.spec = json.loads(text)
        else:
            # Treat as raw JSON/YAML string
            try:
                self.spec = json.loads(self.spec_source)
            except json.JSONDecodeError:
                self.spec = yaml.safe_load(self.spec_source)

        # Resolve $ref references
        self.spec = jsonref.replace_refs(self.spec, proxies=False)

        # Extract base URL
        servers = self.spec.get("servers", [])
        if servers:
            self.base_url = servers[0].get("url", "").rstrip("/")
        else:
            self.base_url = ""

        return self

    def extract_endpoints(self) -> list[EndpointInfo]:
        """Walk all paths and extract endpoint definitions."""
        self.endpoints = []
        paths = self.spec.get("paths", {})

        for path, path_item in paths.items():
            # Path-level parameters apply to all methods
            common_params = self._parse_parameters(path_item.get("parameters", []))

            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                op = path_item.get(method)
                if not op:
                    continue

                operation_id = op.get("operationId", "")
                if not operation_id:
                    # Generate from method + path
                    clean = path.replace("/", "_").replace("{", "").replace("}", "").strip("_")
                    operation_id = f"{method}_{clean}"

                # Sanitize operation_id for Python function names
                operation_id = (
                    operation_id
                    .replace("-", "_")
                    .replace(".", "_")
                    .replace(" ", "_")
                    .replace("/", "_")
                )

                # Merge path-level and operation-level params
                op_params = self._parse_parameters(op.get("parameters", []))
                # Op-level params override path-level by name
                param_names = {p.name for p in op_params}
                merged = [p for p in common_params if p.name not in param_names] + op_params

                endpoint = EndpointInfo(
                    operation_id=operation_id,
                    method=method.upper(),
                    path=path,
                    summary=op.get("summary", ""),
                    description=op.get("description", ""),
                    tags=op.get("tags", []),
                    parameters=merged,
                    request_body=self._parse_request_body(op.get("requestBody")),
                    response_schema=self._parse_response(op.get("responses", {})),
                    security=op.get("security", self.spec.get("security", [])),
                )
                self.endpoints.append(endpoint)

        return self.endpoints

    def _parse_parameters(self, params: list[dict]) -> list[ParameterInfo]:
        result = []
        for p in params:
            schema = p.get("schema", {})
            result.append(ParameterInfo(
                name=p.get("name", ""),
                location=p.get("in", "query"),
                required=p.get("required", False),
                schema=self._simplify_schema(schema),
                description=p.get("description", ""),
            ))
        return result

    def _parse_request_body(self, body: Optional[dict]) -> Optional[dict]:
        if not body:
            return None
        content = body.get("content", {})
        # Prefer JSON
        for mime in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data"):
            if mime in content:
                schema = content[mime].get("schema", {})
                return {
                    "content_type": mime,
                    "schema": self._simplify_schema(schema),
                    "required": body.get("required", False),
                }
        # Fallback: first content type
        if content:
            mime, detail = next(iter(content.items()))
            return {
                "content_type": mime,
                "schema": self._simplify_schema(detail.get("schema", {})),
                "required": body.get("required", False),
            }
        return None

    def _parse_response(self, responses: dict) -> Optional[dict]:
        success = responses.get("200") or responses.get("201") or responses.get("default")
        if not success:
            return None
        content = success.get("content", {})
        if "application/json" in content:
            return self._simplify_schema(content["application/json"].get("schema", {}))
        return None

    def _simplify_schema(self, schema: dict, _seen: set | None = None) -> dict:
        """Flatten nested $ref and keep only essential JSON Schema fields.

        Uses object-id tracking to handle circular $ref references.
        """
        if not schema or not isinstance(schema, dict):
            return {}
        if _seen is None:
            _seen = set()
        obj_id = id(schema)
        if obj_id in _seen:
            # Circular reference — emit a type-only stub
            t = schema.get("type", "object")
            return {"type": t, "$circular": True}
        _seen.add(obj_id)
        try:
            keep = {"type", "properties", "items", "enum", "required", "format",
                    "description", "default", "minimum", "maximum", "minLength",
                    "maxLength", "pattern", "anyOf", "oneOf", "allOf"}
            result = {}
            for k, v in schema.items():
                if k in keep:
                    if k == "properties" and isinstance(v, dict):
                        result[k] = {pk: self._simplify_schema(pv, _seen.copy())
                                     for pk, pv in v.items()}
                    elif k == "items" and isinstance(v, dict):
                        result[k] = self._simplify_schema(v, _seen.copy())
                    elif k in ("anyOf", "oneOf", "allOf") and isinstance(v, list):
                        result[k] = [self._simplify_schema(item, _seen.copy())
                                     for item in v]
                    else:
                        result[k] = copy.deepcopy(v)
            return result
        finally:
            _seen.discard(obj_id)

    def get_security_schemes(self) -> dict:
        """Return defined security schemes from the spec."""
        return self.spec.get("components", {}).get("securitySchemes", {})

    def summary(self) -> dict:
        """Return a human-readable summary of the parsed spec."""
        return {
            "title": self.spec.get("info", {}).get("title", "Unknown"),
            "version": self.spec.get("info", {}).get("version", "Unknown"),
            "description": self.spec.get("info", {}).get("description", ""),
            "base_url": self.base_url,
            "endpoint_count": len(self.endpoints),
            "security_schemes": list(self.get_security_schemes().keys()),
            "tags": list({t for ep in self.endpoints for t in ep.tags}),
        }
