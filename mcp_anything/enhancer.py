"""
LLM-Enhanced Generator - uses an LLM to produce richer MCP tool definitions.

Instead of purely mechanical code generation, this module sends endpoint
descriptions to an LLM to:
  1. Generate better tool descriptions (not just raw summaries)
  2. Infer parameter constraints and examples
  3. Suggest appropriate error handling
  4. Group related tools logically
  5. Generate usage examples
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from mcp_anything.analyzer import EndpointInfo, OpenAPIAnalyzer
from mcp_anything.llm import LLMBackend, create_llm


@dataclass
class EnhancedTool:
    """An LLM-enhanced tool definition."""
    operation_id: str
    func_name: str
    method: str
    path: str
    summary: str
    description: str
    enhanced_description: str  # LLM-generated rich description
    parameters: list[dict]
    request_body_schema: Optional[dict]
    response_schema: Optional[dict]
    tags: list[str]
    examples: list[dict] = field(default_factory=list)
    error_handling: str = ""
    notes: str = ""


SYSTEM_PROMPT = """You are an API documentation expert. You take OpenAPI endpoint definitions and produce enhanced, agent-friendly tool documentation.

For each endpoint, you will provide:
1. A clear, action-oriented description suitable for an AI agent
2. Usage examples showing realistic call patterns
3. Error handling notes (what can go wrong and how to handle it)
4. Parameter constraint notes (any gotchas, required combinations, etc.)

Respond in the exact JSON format requested. Be concise but thorough."""


class LLMEnhancedGenerator:
    """Generate MCP tools with LLM-enhanced descriptions and metadata."""

    def __init__(
        self,
        analyzer: OpenAPIAnalyzer,
        llm: LLMBackend | None = None,
        llm_config: dict | None = None,
        batch_size: int = 5,
    ):
        self.analyzer = analyzer
        self.llm = llm or create_llm(config=llm_config or {})
        self.batch_size = batch_size
        self.enhanced_tools: list[EnhancedTool] = []

    def enhance_all(self) -> list[EnhancedTool]:
        """Enhance all endpoints with LLM-generated descriptions."""
        endpoints = self.analyzer.extract_endpoints()

        # Process in batches to avoid token limits
        for i in range(0, len(endpoints), self.batch_size):
            batch = endpoints[i:i + self.batch_size]
            enhanced = self._enhance_batch(batch)
            self.enhanced_tools.extend(enhanced)

        return self.enhanced_tools

    def _enhance_batch(self, endpoints: list[EndpointInfo]) -> list[EnhancedTool]:
        """Send a batch of endpoints to the LLM for enhancement."""
        endpoint_data = []
        for ep in endpoints:
            endpoint_data.append({
                "operation_id": ep.operation_id,
                "method": ep.method,
                "path": ep.path,
                "summary": ep.summary,
                "description": ep.description,
                "tags": ep.tags,
                "parameters": [
                    {
                        "name": p.name,
                        "location": p.location,
                        "required": p.required,
                        "schema": p.schema,
                        "description": p.description,
                    }
                    for p in ep.parameters
                ],
                "request_body": ep.request_body,
                "response_schema": ep.response_schema,
            })

        prompt = f"""Enhance these {len(endpoint_data)} API endpoint definitions for use as AI agent tools.

Endpoints:
{json.dumps(endpoint_data, indent=2)}

For each endpoint, return a JSON object with:
{{
  "enhanced_tools": [
    {{
      "operation_id": "...",
      "enhanced_description": "Clear, action-oriented description for an AI agent",
      "examples": [
        {{"description": "...", "params": {{"key": "value"}}}}
      ],
      "error_handling": "What can go wrong and how to handle it",
      "notes": "Gotchas, required parameter combinations, rate limits, etc."
    }}
  ]
}}"""

        try:
            result = self.llm.complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.0)
            enhancements = result.get("enhanced_tools", [])
        except Exception as e:
            # Fallback: use raw descriptions if LLM fails
            enhancements = []

        # Merge LLM enhancements with original data
        enhanced = []
        for i, ep in enumerate(endpoints):
            enh = enhancements[i] if i < len(enhancements) else {}

            # Sanitize func name
            func_name = (
                ep.operation_id
                .replace("-", "_")
                .replace(".", "_")
                .replace(" ", "_")
                .replace("/", "_")
            )
            if func_name and func_name[0].isdigit():
                func_name = f"op_{func_name}"
            func_name = func_name.lower()

            enhanced.append(EnhancedTool(
                operation_id=ep.operation_id,
                func_name=func_name,
                method=ep.method,
                path=ep.path,
                summary=ep.summary,
                description=ep.description,
                enhanced_description=enh.get("enhanced_description", ep.summary or ep.description),
                parameters=[
                    {
                        "name": p.name,
                        "location": p.location,
                        "required": p.required,
                        "schema": p.schema,
                        "description": p.description,
                    }
                    for p in ep.parameters
                ],
                request_body_schema=ep.request_body.get("schema") if ep.request_body else None,
                response_schema=ep.response_schema,
                tags=ep.tags,
                examples=enh.get("examples", []),
                error_handling=enh.get("error_handling", ""),
                notes=enh.get("notes", ""),
            ))

        return enhanced

    def get_enhancement_summary(self) -> dict:
        """Return a summary of what was enhanced."""
        return {
            "total_tools": len(self.enhanced_tools),
            "tools_with_examples": sum(1 for t in self.enhanced_tools if t.examples),
            "tools_with_error_handling": sum(1 for t in self.enhanced_tools if t.error_handling),
            "tools_with_notes": sum(1 for t in self.enhanced_tools if t.notes),
            "llm_provider": self.llm.name,
        }
