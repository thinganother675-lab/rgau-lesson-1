"""Network failure and credential handling tests use MockTransport, never live APIs."""

import json

import httpx
import pytest

from sciagg.http import Http
from sciagg.providers.base import ProviderError, attempt
from sciagg.providers.scopus import Scopus


def http_fixture(tmp_path, handler):
    sleeps = []
    http = Http(
        tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
        min_interval=0,
    )
    return http, sleeps


def test_timeout_is_bounded_and_does_not_expose_request_or_secret(tmp_path):
    calls = []

    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("leaked-secret-token", request=request)

    http, sleeps = http_fixture(tmp_path, fail)
    try:
        with pytest.raises(ProviderError) as exc:
            http.get(
                "fixture", "https://example.invalid", headers={"Authorization": "Bearer leaked-secret-token"}
            )
        assert "leaked-secret-token" not in str(exc.value)
        assert len(calls) == 3
        assert len(sleeps) == 2
        assert not list(tmp_path.glob("*.json"))
    finally:
        http.close()


def test_retry_after_is_respected_and_success_is_cached(tmp_path):
    calls = []

    def response(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "2"})
            if len(calls) == 1
            else httpx.Response(200, json={"value": 4})
        )

    http, sleeps = http_fixture(tmp_path, response)
    try:
        assert http.get("fixture", "https://example.invalid") == {"value": 4}
        stamp = http.last_retrieved_at
        assert sleeps == [2]
        assert not http.cache_hit
        assert http.get("fixture", "https://example.invalid") == {"value": 4}
        assert http.cache_hit and http.last_retrieved_at == stamp
        assert len(calls) == 2
    finally:
        http.close()


def test_long_retry_after_reports_without_early_retry(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"})

    http, sleeps = http_fixture(tmp_path, handler)
    try:
        with pytest.raises(ProviderError) as exc:
            http.get("fixture", "https://example.invalid")
        assert exc.value.status == 429
        assert len(calls) == 1 and sleeps == []
    finally:
        http.close()


def test_403_is_not_retried_and_response_body_not_exposed(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403, text="private-response-token")

    http, _ = http_fixture(tmp_path, handler)
    try:
        _, status = attempt("fixture", lambda: http.get("fixture", "https://example.invalid"))
        assert status["http_status"] == 403 and status["status"] == "unavailable"
        assert "private-response-token" not in json.dumps(status)
        assert len(calls) == 1
    finally:
        http.close()


def test_malformed_success_json_is_provider_failure(tmp_path):
    http, _ = http_fixture(tmp_path, lambda request: httpx.Response(200, text="<html>login</html>"))
    try:
        with pytest.raises(ProviderError):
            http.get("fixture", "https://example.invalid")
        assert not list(tmp_path.glob("*.json"))
    finally:
        http.close()


def test_credentials_separate_cache_without_plaintext_persistence(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    http, _ = http_fixture(tmp_path, handler)
    try:
        for token in ("secret-first", "secret-second"):
            http.get(
                "fixture",
                "https://example.invalid",
                params={"api_key": token},
                headers={"Authorization": "Bearer " + token},
            )
        assert len(calls) == 2
        for path in tmp_path.glob("*.json"):
            assert "secret-" not in path.name + path.read_text(encoding="utf-8")
    finally:
        http.close()


def test_url_embedded_credentials_not_persisted(tmp_path):
    http, _ = http_fixture(tmp_path, lambda request: httpx.Response(200, json={"ok": True}))
    try:
        http.get("fixture", "https://example.invalid/data?api_key=secret-in-url")
        assert all("secret-in-url" not in p.read_text(encoding="utf-8") for p in tmp_path.glob("*.json"))
    finally:
        http.close()


def test_offline_uses_expired_snapshot_and_preserves_timestamp(tmp_path):
    http, _ = http_fixture(tmp_path, lambda request: httpx.Response(200, json={"ok": True}))
    try:
        http.get("fixture", "https://example.invalid")
        stamp = http.last_retrieved_at
        http.offline, http.ttl = True, -1
        assert http.get("fixture", "https://example.invalid") == {"ok": True}
        assert http.last_retrieved_at == stamp and http.cache_hit
        with pytest.raises(ProviderError, match="offline"):
            http.get("fixture", "https://example.invalid/missing")
    finally:
        http.close()


def test_missing_scopus_credentials_avoids_network(monkeypatch):
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)

    class NoNetwork:
        def get(self, *args, **kwargs):
            pytest.fail("Missing credentials must not cause a network request")

    result, status = attempt("scopus", lambda: Scopus(NoNetwork()).author("123456"))
    assert result is None
    assert status["status"] == "unavailable" and "SCOPUS_API_KEY" in status["reason"]
