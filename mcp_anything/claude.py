"""
Claude SDK Integration for MCP-Anything.

Uses the Anthropic SDK's native features:
  - tool_use: Claude analyzes APIs and suggests tool definitions via structured tool calls
  - streaming: Real-time generation feedback
  - batch: Process multiple APIs efficiently
  - structured output: Guaranteed JSON schemas for tool definitions

This replaces the generic LLM enhancement with Claude-specific capabilities.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

import anthropic
from anthropic.types import Message, ContentBlock, ToolUseBlock, TextBlock


# ─── Claude Tool Definitions (for tool_use) ──────────────────────────────────

ANALYZE_ENDPOINT_TOOL = {
    "name": "analyze_endpoint",
    "description": "Analyze an API endpoint and produce enhanced MCP tool metadata. Call this for each endpoint that needs analysis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation_id": {
                "type": "string",
                "description": "The original operation ID from the OpenAPI spec"
            },
            "tool_name": {
                "type": "string",
                "description": "A clean, snake_case Python function name for the MCP tool"
            },
            "enhanced_description": {
                "type": "string",
                "description": "Action-oriented description for an AI agent. Start with a verb. Be specific about what data is returned."
            },
            "parameter_docs": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "example": {"type": "string"},
                        "constraints": {"type": "string"}
                    },
                    "required": ["description"]
                },
                "description": "Enhanced documentation for each parameter, keyed by parameter name"
            },
            "usage_examples": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scenario": {"type": "string"},
                        "params": {"type": "object"}
                    },
                    "required": ["scenario", "params"]
                },
                "description": "2-3 realistic usage examples showing different scenarios"
            },
            "error_scenarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string"},
                        "status_code": {"type": "integer"},
                        "handling": {"type": "string"}
                    },
                    "required": ["condition", "handling"]
                },
                "description": "Common error scenarios and recommended handling"
            },
            "prerequisites": {
                "type": "string",
                "description": "Any prerequisites: authentication, prior API calls, rate limits, etc."
            },
            "related_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Operation IDs of related endpoints that are typically called together"
            }
        },
        "required": ["operation_id", "tool_name", "enhanced_description"]
    }
}

GROUP_TOOLS_TOOL = {
    "name": "group_tools",
    "description": "Suggest logical groupings for a set of API tools. Groups should reflect common workflows.",
    "input_schema": {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Group name (e.g., 'user_management', 'data_retrieval')"},
                        "description": {"type": "string", "description": "What this group of tools accomplishes"},
                        "tools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Operation IDs belonging to this group"
                        },
                        "common_workflow": {
                            "type": "string",
                            "description": "A typical workflow using these tools in sequence"
                        }
                    },
                    "required": ["name", "description", "tools"]
                }
            }
        },
        "required": ["groups"]
    }
}

GENERATE_TEST_TOOL = {
    "name": "generate_test_cases",
    "description": "Generate test cases for an MCP tool based on the endpoint definition.",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation_id": {"type": "string"},
            "test_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "params": {"type": "object"},
                        "expected_status": {"type": "integer"},
                        "assertions": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["name", "params", "assertions"]
                }
            }
        },
        "required": ["operation_id", "test_cases"]
    }
}


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class ClaudeEnhancedEndpoint:
    """Endpoint enhanced by Claude's tool_use analysis."""
    operation_id: str
    tool_name: str
    enhanced_description: str = ""
    parameter_docs: dict = field(default_factory=dict)
    usage_examples: list[dict] = field(default_factory=list)
    error_scenarios: list[dict] = field(default_factory=list)
    prerequisites: str = ""
    related_tools: list[str] = field(default_factory=list)
    # Original endpoint data
    method: str = ""
    path: str = ""
    original_summary: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    request_body: Optional[dict] = None
    response_schema: Optional[dict] = None


@dataclass
class ToolGroup:
    """Logical grouping of related tools."""
    name: str
    description: str
    tools: list[str]
    common_workflow: str = ""


# ─── Claude Integration Class ───────────────────────────────────────────────

class ClaudeIntegration:
    """Claude SDK integration for MCP-Anything.

    Uses Anthropic's native tool_use for structured analysis instead of
    raw text generation. This gives us:
    - Guaranteed structured output (no JSON parsing failures)
    - Richer metadata (examples, errors, constraints per tool)
    - Tool grouping suggestions
    - Test case generation
    - Streaming for real-time feedback
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 8192,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self._client: Optional[anthropic.Anthropic] = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def analyze_endpoints(
        self,
        endpoints: list[dict],
        api_context: dict,
        batch_size: int = 5,
        on_progress: Callable | None = None,
    ) -> list[ClaudeEnhancedEndpoint]:
        """Analyze endpoints using Claude's tool_use.

        Args:
            endpoints: List of endpoint dicts from OpenAPI analyzer
            api_context: API metadata (title, description, base_url, etc.)
            batch_size: Number of endpoints to analyze per Claude call
            on_progress: Optional callback(enhanced_count, total)
        """
        enhanced = []
        total = len(endpoints)

        for i in range(0, total, batch_size):
            batch = endpoints[i:i + batch_size]
            batch_result = self._analyze_batch(batch, api_context)
            enhanced.extend(batch_result)

            if on_progress:
                on_progress(len(enhanced), total)

        return enhanced

    def _analyze_batch(
        self,
        endpoints: list[dict],
        api_context: dict,
    ) -> list[ClaudeEnhancedEndpoint]:
        """Send a batch of endpoints to Claude for analysis via tool_use."""
        endpoint_summary = json.dumps(endpoints, indent=2)
        api_info = json.dumps(api_context, indent=2)

        system_prompt = f"""You are an API documentation expert specializing in creating agent-friendly tool interfaces.

You are analyzing endpoints from: {api_context.get('title', 'Unknown API')}
Description: {api_context.get('description', 'N/A')[:500]}
Base URL: {api_context.get('base_url', 'N/A')}

For each endpoint, call the analyze_endpoint tool with:
1. A clean, Pythonic tool_name (snake_case)
2. An enhanced_description that starts with a verb and tells the agent exactly what happens
3. Parameter documentation with examples and constraints
4. 2-3 realistic usage examples
5. Error scenarios with handling recommendations
6. Any prerequisites (auth, rate limits, dependencies on other calls)
7. Related tools that are typically used together

Analyze ALL {len(endpoints)} endpoints in this batch. Call analyze_endpoint once per endpoint."""

        user_message = f"Analyze these endpoints:\n\n{endpoint_summary}"

        # Make the API call with tool_use
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            tools=[ANALYZE_ENDPOINT_TOOL],
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract tool_use results
        return self._parse_analysis_response(response, endpoints)

    def _parse_analysis_response(
        self,
        response: Message,
        original_endpoints: list[dict],
    ) -> list[ClaudeEnhancedEndpoint]:
        """Parse Claude's tool_use response into enhanced endpoints."""
        enhanced = []

        # Build lookup from original endpoints
        ep_lookup = {ep["operation_id"]: ep for ep in original_endpoints}

        for block in response.content:
            if isinstance(block, ToolUseBlock) and block.name == "analyze_endpoint":
                data = block.input
                op_id = data.get("operation_id", "")
                original = ep_lookup.get(op_id, {})

                enhanced.append(ClaudeEnhancedEndpoint(
                    operation_id=op_id,
                    tool_name=data.get("tool_name", op_id.lower().replace("-", "_")),
                    enhanced_description=data.get("enhanced_description", ""),
                    parameter_docs=data.get("parameter_docs", {}),
                    usage_examples=data.get("usage_examples", []),
                    error_scenarios=data.get("error_scenarios", []),
                    prerequisites=data.get("prerequisites", ""),
                    related_tools=data.get("related_tools", []),
                    method=original.get("method", ""),
                    path=original.get("path", ""),
                    original_summary=original.get("summary", ""),
                    tags=original.get("tags", []),
                    parameters=original.get("parameters", []),
                    request_body=original.get("request_body"),
                    response_schema=original.get("response_schema"),
                ))

        # Fill in any endpoints Claude didn't analyze
        analyzed_ids = {e.operation_id for e in enhanced}
        for ep in original_endpoints:
            if ep["operation_id"] not in analyzed_ids:
                enhanced.append(ClaudeEnhancedEndpoint(
                    operation_id=ep["operation_id"],
                    tool_name=ep["operation_id"].lower().replace("-", "_").replace(".", "_"),
                    enhanced_description=ep.get("summary", ep.get("description", "")),
                    method=ep.get("method", ""),
                    path=ep.get("path", ""),
                    original_summary=ep.get("summary", ""),
                    tags=ep.get("tags", []),
                    parameters=ep.get("parameters", []),
                    request_body=ep.get("request_body"),
                    response_schema=ep.get("response_schema"),
                ))

        return enhanced

    def suggest_groups(
        self,
        enhanced_endpoints: list[ClaudeEnhancedEndpoint],
    ) -> list[ToolGroup]:
        """Ask Claude to suggest logical tool groupings."""
        tool_info = [
            {
                "operation_id": ep.operation_id,
                "tool_name": ep.tool_name,
                "method": ep.method,
                "path": ep.path,
                "description": ep.enhanced_description or ep.original_summary,
                "tags": ep.tags,
            }
            for ep in enhanced_endpoints
        ]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system="You are an API design expert. Group related tools into logical workflow-oriented groups.",
            tools=[GROUP_TOOLS_TOOL],
            messages=[{
                "role": "user",
                "content": f"Group these tools into logical workflows:\n\n{json.dumps(tool_info, indent=2)}"
            }],
        )

        groups = []
        for block in response.content:
            if isinstance(block, ToolUseBlock) and block.name == "group_tools":
                for g in block.input.get("groups", []):
                    groups.append(ToolGroup(
                        name=g["name"],
                        description=g["description"],
                        tools=g["tools"],
                        common_workflow=g.get("common_workflow", ""),
                    ))

        return groups

    def generate_tests(
        self,
        enhanced_endpoint: ClaudeEnhancedEndpoint,
    ) -> list[dict]:
        """Ask Claude to generate test cases for a specific tool."""
        ep_data = {
            "operation_id": enhanced_endpoint.operation_id,
            "tool_name": enhanced_endpoint.tool_name,
            "method": enhanced_endpoint.method,
            "path": enhanced_endpoint.path,
            "description": enhanced_endpoint.enhanced_description,
            "parameters": enhanced_endpoint.parameters,
            "request_body": enhanced_endpoint.request_body,
            "error_scenarios": enhanced_endpoint.error_scenarios,
        }

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system="You are a QA engineer. Generate comprehensive test cases for API tools.",
            tools=[GENERATE_TEST_TOOL],
            messages=[{
                "role": "user",
                "content": f"Generate test cases for this tool:\n\n{json.dumps(ep_data, indent=2)}"
            }],
        )

        for block in response.content:
            if isinstance(block, ToolUseBlock) and block.name == "generate_test_cases":
                return block.input.get("test_cases", [])

        return []

    def analyze_streaming(
        self,
        endpoints: list[dict],
        api_context: dict,
    ):
        """Stream Claude's analysis in real-time.

        Yields partial results as they become available.
        This is useful for showing progress in a UI.
        """
        endpoint_summary = json.dumps(endpoints[:10], indent=2)  # Limit for streaming

        system_prompt = f"""Analyze these API endpoints and provide enhanced descriptions.
For each endpoint, explain:
1. What the tool does (action-oriented)
2. Key parameters and their purpose
3. What the agent should expect in the response

Be concise but thorough."""

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Analyze these endpoints:\n\n{endpoint_summary}"}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def enhance_with_claude(
        self,
        endpoints: list[dict],
        api_context: dict,
        include_groups: bool = True,
        include_tests: bool = False,
        batch_size: int = 5,
    ) -> dict:
        """Full Claude enhancement pipeline.

        Returns a complete enhancement package:
        - enhanced_endpoints: List of ClaudeEnhancedEndpoint
        - groups: Tool groupings (if include_groups)
        - tests: Test cases (if include_tests)
        - summary: Statistics about the enhancement
        """
        # Step 1: Analyze all endpoints
        enhanced = self.analyze_endpoints(endpoints, api_context, batch_size)

        result = {
            "enhanced_endpoints": enhanced,
            "groups": [],
            "tests": {},
            "summary": {},
        }

        # Step 2: Suggest groupings
        if include_groups:
            result["groups"] = self.suggest_groups(enhanced)

        # Step 3: Generate tests (for first few endpoints to avoid token costs)
        if include_tests:
            for ep in enhanced[:5]:  # Limit to avoid excessive API calls
                tests = self.generate_tests(ep)
                if tests:
                    result["tests"][ep.operation_id] = tests

        # Step 4: Summary
        result["summary"] = {
            "total_endpoints": len(enhanced),
            "with_examples": sum(1 for e in enhanced if e.usage_examples),
            "with_error_handling": sum(1 for e in enhanced if e.error_scenarios),
            "with_prerequisites": sum(1 for e in enhanced if e.prerequisites),
            "groups_suggested": len(result["groups"]),
            "tests_generated": sum(len(t) for t in result["tests"].values()),
            "model": self.model,
        }

        return result
