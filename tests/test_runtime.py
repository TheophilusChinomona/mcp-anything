import json
from pathlib import Path

import httpx
import pytest

from mcp_anything.runtime import (
    AuthSession,
    CapabilityDenied,
    CapabilityPolicy,
    MCPHttpClient,
)


def test_read_only_policy_denies_state_changes_by_default():
    policy = CapabilityPolicy()

    with pytest.raises(CapabilityDenied):
        policy.check("POST", "create_client", ["Client"])

    policy.check("GET", "list_clients", ["Client"])



def test_explicit_method_allowlist_denies_head_and_options(monkeypatch):
    monkeypatch.setenv("SPECCON_DEVPM_ALLOWED_METHODS", "GET")
    policy = CapabilityPolicy.from_env("SPECCON_DEVPM")

    policy.check("GET", "list_projects")
    for method in ("HEAD", "OPTIONS"):
        with pytest.raises(CapabilityDenied):
            policy.check(method, "list_projects")

def test_auth_session_logs_in_and_refreshes_with_valid_tokens():
    calls = []
    responses = [
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-1",
                    "refreshToken": "refresh-1",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-2",
                    "refreshToken": "refresh-2",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
    ]

    def handler(request):
        calls.append(request)
        return responses.pop(0)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    session = AuthSession(
        "https://example.test",
        email="user@example.test",
        password="secret",
        client=client,
    )

    assert session.get_token() == "access-1"
    assert session.get_token() == "access-1"
    assert session.get_token(force_refresh=True) == "access-2"
    assert [request.url.path for request in calls] == [
        "/api/User/Login",
        "/api/User/RefreshToken",
    ]


def test_http_client_refreshes_and_retries_safe_get_after_401():
    calls = []
    responses = [
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-1",
                    "refreshToken": "refresh-1",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
        httpx.Response(401, json={"message": "expired"}),
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-2",
                    "refreshToken": "refresh-2",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
        httpx.Response(200, json={"ok": True}),
    ]

    def handler(request):
        calls.append(request)
        return responses.pop(0)

    transport_client = httpx.Client(transport=httpx.MockTransport(handler))
    session = AuthSession(
        "https://example.test",
        email="user@example.test",
        password="secret",
        client=transport_client,
    )
    api = MCPHttpClient(session, CapabilityPolicy(), client=transport_client)

    assert api.request("GET", "/api/Clients") == {"ok": True}
    assert [request.url.path for request in calls] == [
        "/api/User/Login",
        "/api/Clients",
        "/api/User/RefreshToken",
        "/api/Clients",
    ]


def test_http_client_retries_post_once_after_401_with_fresh_token():
    calls = []
    responses = [
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-1",
                    "refreshToken": "refresh-1",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
        httpx.Response(401, json={"message": "expired"}),
        httpx.Response(
            200,
            json={
                "isError": False,
                "result": {
                    "token": "access-2",
                    "refreshToken": "refresh-2",
                    "validTo": "2099-01-01T00:00:00Z",
                },
            },
        ),
        httpx.Response(200, json={"isError": False, "result": {"id": 42}}),
    ]

    def handler(request):
        calls.append(request)
        return responses.pop(0)

    transport_client = httpx.Client(transport=httpx.MockTransport(handler))
    session = AuthSession(
        "https://example.test",
        email="user@example.test",
        password="secret",
        client=transport_client,
    )
    api = MCPHttpClient(
        session,
        CapabilityPolicy(allow_writes=True),
        client=transport_client,
    )

    result = api.request("POST", "/api/Clients", body={"name": "Acme"})

    assert [request.url.path for request in calls] == [
        "/api/User/Login",
        "/api/Clients",
        "/api/User/RefreshToken",
        "/api/Clients",
    ]
    assert result["result"]["id"] == 42


def test_http_client_serializes_form_and_multipart_requests(tmp_path):
    captured = []
    upload = tmp_path / "evidence.txt"
    upload.write_text("evidence")

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    transport_client = httpx.Client(transport=httpx.MockTransport(handler))
    session = AuthSession(
        "https://example.test",
        static_token="static-token",
        client=transport_client,
    )
    api = MCPHttpClient(
        session,
        CapabilityPolicy(allow_writes=True),
        client=transport_client,
    )

    api.request(
        "POST",
        "/api/form",
        body={"name": "Acme"},
        content_type="application/x-www-form-urlencoded",
    )
    api.request(
        "POST",
        "/api/upload",
        body={"description": "proof", "files": {"document": str(upload)}},
        content_type="multipart/form-data",
    )

    assert "application/x-www-form-urlencoded" in captured[0].headers["content-type"]
    assert "multipart/form-data" in captured[1].headers["content-type"]
    assert b"evidence" in captured[1].content


def test_http_client_sends_header_and_cookie_parameters():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    transport_client = httpx.Client(transport=httpx.MockTransport(handler))
    session = AuthSession(
        "https://example.test",
        static_token="static-token",
        client=transport_client,
    )
    api = MCPHttpClient(
        session,
        CapabilityPolicy(),
        client=transport_client,
    )

    api.request(
        "GET",
        "/api/profile",
        headers={"X-Tenant": "tenant-1"},
        cookies={"session": "cookie-1"},
    )

    assert captured[0].headers["X-Tenant"] == "tenant-1"
    assert "session=cookie-1" in captured[0].headers["Cookie"]


class TestCapabilityPolicyFilters:
    """Combined policy filter tests for CapabilityPolicy.check()."""

    def test_denied_operations_blocked_before_allowlist(self):
        policy = CapabilityPolicy(
            allowed_operations={"create_ticket", "update_ticket"},
            denied_operations={"update_ticket"},
            allow_writes=True,
        )
        policy.check("POST", "create_ticket")  # should pass
        with pytest.raises(CapabilityDenied):
            policy.check("POST", "update_ticket")  # denied despite being in allowed

    def test_operation_outside_allowlist_denied(self):
        policy = CapabilityPolicy(
            allowed_operations={"list_projects"},
        )
        with pytest.raises(CapabilityDenied):
            policy.check("GET", "list_tickets")
        policy.check("GET", "list_projects")  # allowed

    def test_method_outside_allowlist_denied(self):
        policy = CapabilityPolicy(
            allowed_methods={"GET", "POST"},
            allow_writes=True,
        )
        policy.check("GET", "read_project")
        policy.check("POST", "create_ticket")
        with pytest.raises(CapabilityDenied):
            policy.check("PUT", "update_ticket")

    def test_empty_allowlist_allows_all_methods(self):
        policy = CapabilityPolicy(allow_writes=True)
        # No enforced method allowlist — all methods pass
        policy.check("GET", "list")
        policy.check("POST", "create")
        policy.check("PUT", "update")
        policy.check("DELETE", "delete")

    def test_policy_from_env_parses_all_fields(self, monkeypatch):
        monkeypatch.setenv("TEST_MCP_ALLOWED_METHODS", "GET,POST")
        monkeypatch.setenv("TEST_MCP_ALLOWED_OPERATIONS", "list_tickets,create_ticket")
        monkeypatch.setenv("TEST_MCP_DENIED_OPERATIONS", "delete_ticket")
        monkeypatch.setenv("TEST_MCP_ALLOW_WRITES", "true")
        policy = CapabilityPolicy.from_env("TEST_MCP")
        assert policy.allowed_methods == {"GET", "POST"}
        assert policy.allowed_operations == {"list_tickets", "create_ticket"}
        assert policy.denied_operations == {"delete_ticket"}
        assert policy.allow_writes is True

    def test_combined_filter_denied_takes_priority(self):
        policy = CapabilityPolicy(
            allowed_operations={"list_pets", "delete_pet"},
            denied_operations={"delete_pet"},
        )
        policy.check("GET", "list_pets")  # allowed
        with pytest.raises(CapabilityDenied) as exc:
            policy.check("DELETE", "delete_pet")
        assert "denied" in str(exc.value).lower()
