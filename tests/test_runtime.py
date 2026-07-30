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


def test_http_client_does_not_retry_non_idempotent_post_after_401():
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

    with pytest.raises(httpx.HTTPStatusError):
        api.request("POST", "/api/Clients", body={"name": "Acme"})

    assert [request.url.path for request in calls] == [
        "/api/User/Login",
        "/api/Clients",
    ]


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
