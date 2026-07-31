"""Shared runtime for generated MCP servers.

The module is intentionally dependency-light so generated servers can copy it
alongside their server module and run without importing the generator package.
"""

from __future__ import annotations

import mimetypes
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

import httpx


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
DEFAULT_TOKEN_TTL_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class AuthenticationError(RuntimeError):
    """Raised when login or token refresh cannot produce a usable token."""


class CapabilityDenied(PermissionError):
    """Raised when a tool is outside the configured capability profile."""


class CapabilityPolicy:
    """Enforce read/write and operation/tag allowlists at request time."""

    def __init__(
        self,
        *,
        allow_writes: bool = False,
        allowed_tags: Optional[set[str]] = None,
        allowed_operations: Optional[set[str]] = None,
        denied_operations: Optional[set[str]] = None,
        allowed_methods: Optional[set[str]] = None,
    ):
        self.allow_writes = allow_writes
        self.allowed_tags = {tag for tag in (allowed_tags or set()) if tag}
        self.allowed_operations = {op for op in (allowed_operations or set()) if op}
        self.denied_operations = {op for op in (denied_operations or set()) if op}
        self.allowed_methods = {
            method.upper() for method in (allowed_methods or set()) if method
        }

    @classmethod
    def from_env(cls, prefix: str = "MCP") -> "CapabilityPolicy":
        prefix = prefix.upper()

        def csv(name: str) -> set[str]:
            return {
                value.strip()
                for value in os.environ.get(f"{prefix}_{name}", "").split(",")
                if value.strip()
            }

        return cls(
            allow_writes=os.environ.get(f"{prefix}_ALLOW_WRITES", "false").lower()
            in {"1", "true", "yes"},
            allowed_methods=csv("ALLOWED_METHODS") or None,
            allowed_tags=csv("ALLOWED_TAGS"),
            allowed_operations=csv("ALLOWED_OPERATIONS"),
            denied_operations=csv("DENIED_OPERATIONS"),
        )

    def check(self, method: str, operation_id: str = "", tags: Optional[list[str]] = None) -> None:
        method = method.upper()
        if operation_id and operation_id in self.denied_operations:
            raise CapabilityDenied(f"Operation is denied: {operation_id}")
        if self.allowed_operations and operation_id not in self.allowed_operations:
            raise CapabilityDenied(f"Operation is not allowlisted: {operation_id}")
        if self.allowed_tags and not self.allowed_tags.intersection(tags or []):
            raise CapabilityDenied(f"Operation tags are not allowlisted: {', '.join(tags or [])}")
        if self.allowed_methods and method not in self.allowed_methods:
            raise CapabilityDenied(f"HTTP method is not allowlisted: {method}")
        if method not in SAFE_METHODS and not self.allow_writes:
            raise CapabilityDenied("State-changing operations are disabled")


class AuthSession:
    """Manage login credentials, access tokens, and refresh tokens in memory."""

    def __init__(
        self,
        base_url: str,
        *,
        email: str = "",
        password: str = "",
        static_token: str = "",
        client: Optional[httpx.Client] = None,
        clock: Callable[[], float] = time.time,
    ):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.static_token = static_token
        self._client = client or httpx.Client(timeout=30)
        self._owns_client = client is None
        self._clock = clock
        self._lock = threading.RLock()
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at = 0.0

    @property
    def uses_static_token(self) -> bool:
        return bool(self.static_token)

    def _parse_expiry(self, value: Any) -> float:
        if not value:
            return self._clock() + DEFAULT_TOKEN_TTL_SECONDS
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return self._clock() + DEFAULT_TOKEN_TTL_SECONDS

    @staticmethod
    def _extract_auth_result(body: Any) -> tuple[str, str, Any]:
        if not isinstance(body, dict):
            raise AuthenticationError("Authentication response was not an object")
        if body.get("isError"):
            raise AuthenticationError("Authentication request was rejected")
        result = body.get("result")
        if isinstance(result, str):
            token = result
            refresh_token = ""
            valid_to = None
        elif isinstance(result, dict):
            token = result.get("token") or result.get("accessToken") or ""
            refresh_token = result.get("refreshToken") or ""
            valid_to = result.get("validTo")
        else:
            raise AuthenticationError("Authentication response did not contain a token")
        if not isinstance(token, str) or not token:
            raise AuthenticationError("Authentication response did not contain a token")
        return token, refresh_token, valid_to

    def _login(self) -> str:
        if not self.email or not self.password:
            raise AuthenticationError("SPECCON_EMAIL and SPECCON_PASSWORD are required")
        response = self._client.post(
            f"{self.base_url}/api/User/Login",
            json={"email": self.email, "password": self.password},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        token, refresh_token, valid_to = self._extract_auth_result(response.json())
        self._token = token
        self._refresh_token = refresh_token
        self._expires_at = self._parse_expiry(valid_to)
        return token

    def _refresh(self) -> str:
        if not self._refresh_token:
            return self._login()
        response = self._client.post(
            f"{self.base_url}/api/User/RefreshToken",
            json={"accessToken": self._token, "refreshToken": self._refresh_token},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            response.raise_for_status()
            token, refresh_token, valid_to = self._extract_auth_result(response.json())
        except (httpx.HTTPError, ValueError, TypeError, AuthenticationError):
            return self._login()
        self._token = token
        self._refresh_token = refresh_token or self._refresh_token
        self._expires_at = self._parse_expiry(valid_to)
        return token

    def get_token(self, *, force_refresh: bool = False) -> str:
        if self.static_token:
            return self.static_token
        with self._lock:
            if not force_refresh and self._token and self._clock() < self._expires_at - 60:
                return self._token
            return self._refresh() if self._refresh_token else self._login()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class MCPHttpClient:
    """Send policy-checked, authenticated JSON/form/multipart requests."""

    def __init__(
        self,
        auth: AuthSession,
        policy: Optional[CapabilityPolicy] = None,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ):
        self.auth = auth
        self.policy = policy or CapabilityPolicy()
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self.timeout = timeout
        self.max_upload_bytes = max_upload_bytes

    def _headers(
        self,
        content_type: str,
        extra_headers: Optional[Mapping[str, str]] = None,
        cookies: Optional[Mapping[str, str]] = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        token = self.auth.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if content_type in {"application/json", "application/x-www-form-urlencoded"}:
            headers["Content-Type"] = content_type
        headers.update(extra_headers or {})
        if cookies:
            headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
        return headers

    def _multipart_payload(
        self,
        body: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
        fields = dict(body)
        raw_files = fields.pop("files", {}) or {}
        if not isinstance(raw_files, Mapping):
            raise ValueError("multipart body 'files' must be an object mapping field names to paths")
        handles = []
        files = {}
        for field, raw_path in raw_files.items():
            path = Path(str(raw_path)).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Upload file does not exist: {field}")
            if path.stat().st_size > self.max_upload_bytes:
                raise ValueError(f"Upload file exceeds the configured size limit: {field}")
            handle = path.open("rb")
            handles.append(handle)
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            files[str(field)] = (path.name, handle, mime)
        return fields, files, handles

    def _send(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]],
        headers: Optional[Mapping[str, str]],
        cookies: Optional[Mapping[str, str]],
        body: Optional[Mapping[str, Any]],
        content_type: str,
    ) -> httpx.Response:
        kwargs: dict[str, Any] = {
            "params": params or {},
            "headers": self._headers(content_type, headers, cookies),
            "timeout": self.timeout,
        }
        if body is not None:
            if content_type == "application/json":
                kwargs["json"] = body
            elif content_type == "application/x-www-form-urlencoded":
                kwargs["data"] = body
            elif content_type == "multipart/form-data":
                fields, files, handles = self._multipart_payload(body)
                kwargs["data"] = fields
                kwargs["files"] = files
                try:
                    return self._client.request(method, url, **kwargs)
                finally:
                    for handle in handles:
                        handle.close()
            else:
                raise ValueError(f"Unsupported request content type: {content_type}")
        return self._client.request(method, url, **kwargs)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        cookies: Optional[Mapping[str, str]] = None,
        body: Optional[Mapping[str, Any]] = None,
        content_type: str = "application/json",
        operation_id: str = "",
        tags: Optional[list[str]] = None,
    ) -> Any:
        method = method.upper()
        self.policy.check(method, operation_id, tags)
        url = self.auth.base_url.rstrip("/") + path
        response = self._send(
            method,
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            body=body,
            content_type=content_type,
        )
        if response.status_code == 401 and not self.auth.uses_static_token:
            # A 401 means the backend's authorization middleware rejected the
            # request before the handler ran, so the operation was NOT applied.
            # Refresh the token once and retry — matching the GET path — so a
            # long-running server does not fail every write after its access
            # token is revoked or expires server-side. Safe to retry: the write
            # never executed. (If a backend ever returns 401 from inside the
            # handler after doing work, this would double-apply; [Authorize]-style
            # pipelines reject before the action.)
            self.auth.get_token(force_refresh=True)
            response = self._send(
                method,
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                body=body,
                content_type=content_type,
            )
        response.raise_for_status()
        if response.status_code == 204:
            return {"status": "success", "code": 204}
        try:
            return response.json()
        except (ValueError, TypeError):
            return {"status": "success", "text": response.text[:2000]}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
        self.auth.close()
