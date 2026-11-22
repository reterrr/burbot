import asyncio
import ipaddress
import socket
import ssl

import httpx
import pytest

from monitoring import discovery
from monitoring.onboarding_config import ApprovalPolicy, parse_config
from monitoring.security import MonitoringError
from sources.schemas.enums import SourceState as State

pytestmark = pytest.mark.asyncio
PAGE = b"<!doctype html><html><body><main>Public project information</main></body></html>"


async def public_addresses(host):
    return (ipaddress.ip_address("93.184.216.34"),)


async def unthrottled(origin):
    return None


def html_response(content, status=200, content_type="text/html"):
    return httpx.Response(
        status, headers={"Content-Type": content_type}, stream=httpx.ByteStream(content)
    )


async def test_https_request_uses_dns_pinning_and_validates_redirect(monkeypatch):
    lookups = []

    async def addresses(host):
        lookups.append(host)
        return await public_addresses(host)

    monkeypatch.setattr(discovery, "resolve_addresses", addresses)
    seen = []

    async def transport(request):
        host = request.headers["host"]
        seen.append(host)
        assert request.url.host == "93.184.216.34"
        assert request.extensions["sni_hostname"] == host
        assert "cookie" not in request.headers and "authorization" not in request.headers
        if host == "example.org":
            return httpx.Response(
                302, headers={"Location": "https://www.example.org/index", "Set-Cookie": "x=y"}
            )
        return html_response(PAGE)

    policy = ApprovalPolicy(origins=["https://example.org", "https://www.example.org"])
    result = await discovery.probe_html(
        "https://example.org/path", policy, unthrottled, 2, transport=httpx.MockTransport(transport)
    )
    assert result.state == State.ACTIVE and result.code == "HTML_VALIDATED"
    assert result.redirects == 1
    assert set(result.visited_origins) == set(policy.origins)
    assert lookups == seen == ["example.org", "www.example.org"]


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "100.64.1.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "64:ff9b::a00:1",
        "2002:a00:1::1",
        "224.0.0.1",
    ],
)
async def test_discovery_blocks_mixed_public_and_nonpublic_dns(monkeypatch, ip):
    async def mixed(host):
        return (ipaddress.ip_address("93.184.216.34"), ipaddress.ip_address(ip))

    def unexpected(request):
        pytest.fail("Discovery made a connection for a mixed DNS answer")

    monkeypatch.setattr(discovery, "resolve_addresses", mixed)
    outcome = await discovery.probe_html(
        "https://example.org",
        ApprovalPolicy(origins=["https://example.org"]),
        unthrottled,
        2,
        transport=httpx.MockTransport(unexpected),
    )
    assert outcome.code == "NON_PUBLIC_ADDRESS" and not outcome.retryable


@pytest.mark.parametrize(
    "location,code",
    [
        ("https://elsewhere.example.org/", "ORIGIN_NOT_APPROVED"),
        ("https://127.0.0.1/", "UNSAFE_REDIRECT"),
        ("http://example.org/", "UNSAFE_REDIRECT"),
        ("https://user:password@example.org/", "UNSAFE_REDIRECT"),
        ("https://example.org/?access_token=hidden", "UNSAFE_REDIRECT"),
    ],
)
async def test_never_connects_to_unapproved_redirect(monkeypatch, location, code):
    monkeypatch.setattr(discovery, "resolve_addresses", public_addresses)
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": location})

    result = await discovery.probe_html(
        "https://example.org",
        ApprovalPolicy(origins=["https://example.org"]),
        unthrottled,
        2,
        transport=httpx.MockTransport(handler),
    )
    assert result.code == code and calls == 1


@pytest.mark.parametrize(
    "status, content, content_type, code, retryable",
    [
        (200, b"Not a document", "text/html", "INVALID_HTML", False),
        (
            200,
            b"<html><body><div></div><script>load()</script></body></html>",
            "text/html",
            "RENDERED_VALIDATION_REQUIRED",
            False,
        ),
        (
            200,
            b"<html><body>Please sign in<input type=password></body></html>",
            "text/html",
            "AUTHENTICATION_REQUIRED",
            False,
        ),
        (200, PAGE, "application/pdf", "UNSUPPORTED_MEDIA_TYPE", False),
        (403, PAGE, "text/html", "ACCESS_RESTRICTED", False),
        (404, PAGE, "text/html", "HTTP_NOT_FOUND", False),
        (429, PAGE, "text/html", "HTTP_RETRYABLE", True),
        (503, PAGE, "text/html", "HTTP_RETRYABLE", True),
    ],
)
async def test_validation_classifies_http_responses(
    monkeypatch, status, content, content_type, code, retryable
):
    monkeypatch.setattr(discovery, "resolve_addresses", public_addresses)
    outcome = await discovery.probe_html(
        "https://example.org",
        ApprovalPolicy(origins=["https://example.org"]),
        unthrottled,
        2,
        transport=httpx.MockTransport(lambda request: html_response(content, status, content_type)),
    )
    assert outcome.code == code
    assert outcome.retryable == retryable and outcome.http_status == status
    assert outcome.state != State.ACTIVE


async def test_deadline_and_transport_diagnostics(monkeypatch):
    policy = ApprovalPolicy(origins=["https://example.org"])

    async def delayed(host):
        await asyncio.sleep(5)
        return await public_addresses(host)

    monkeypatch.setattr(discovery, "resolve_addresses", delayed)
    result = await discovery.probe_html("https://example.org", policy, unthrottled, 0.02)
    assert result.code == "HTTP_TIMEOUT" and result.retryable

    async def unknown(host):
        raise socket.gaierror(socket.EAI_NONAME)

    monkeypatch.setattr(discovery, "resolve_addresses", unknown)
    result = await discovery.probe_html("https://example.org", policy, unthrottled, 1)
    assert result.code == "DNS_LOOKUP_FAILED" and result.retryable

    def bad_certificate(request):
        raise httpx.ConnectError("private parameters") from ssl.SSLCertVerificationError()

    monkeypatch.setattr(discovery, "resolve_addresses", public_addresses)
    result = await discovery.probe_html(
        "https://example.org",
        policy,
        unthrottled,
        1,
        transport=httpx.MockTransport(bad_certificate),
    )
    assert result.diagnostics()["code"] == "TLS_VALIDATION_FAILED"
    assert not result.retryable and "private" not in str(result.diagnostics())


async def test_policy_requires_exact_https_origins():
    for value in ("http://example.org", "https://*.example.org", "https://example.org/private"):
        with pytest.raises(MonitoringError, match="ONBOARDING_CONFIG_INVALID"):
            parse_config(f'{{"policies":{{"test":{{"origins":["{value}"]}}}}}}')


async def test_same_origin_redirect_shares_rate_reservation_and_rechecks_dns(monkeypatch):
    queried = []
    reservations = []

    async def addresses(host):
        queried.append(host)
        return await public_addresses(host)

    async def reserve(site):
        reservations.append(site)

    def handler(request):
        if request.url.path == "/":
            return httpx.Response(302, headers={"Location": "/home"})
        return html_response(PAGE)

    monkeypatch.setattr(discovery, "resolve_addresses", addresses)
    result = await discovery.probe_html(
        "https://example.org",
        ApprovalPolicy(origins=["https://example.org"]),
        reserve,
        2,
        transport=httpx.MockTransport(handler),
    )
    assert result.state == State.ACTIVE and result.redirects == 1
    assert queried == ["example.org", "example.org"]
    assert reservations == ["https://example.org"]
