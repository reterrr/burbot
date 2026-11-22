"""Bounded HTML validation over allowlisted, DNS-pinned HTTPS connections."""

import asyncio
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import httpx
from lxml import etree, html

from extraction.schemas.common import utc_now
from monitoring.security import MonitoringError, origin
from sources.schemas.enums import SourceState as State

MAX_REDIRECTS = 4
MAX_SAMPLE_BYTES = 256 * 1024
HTML_MEDIA_TYPES = {"text/html", "application/xhtml+xml"}
HTML_MARKUP = re.compile(rb"<(?:!doctype\s+html|html|head|body|main|title|div|p|h[1-6])\b", re.I)
GLOBAL_IPV6 = ipaddress.IPv6Network("2000::/3")


@dataclass(frozen=True)
class ProbeResult:
    state: State
    code: str
    retryable: bool = False
    http_status: int | None = None
    redirects: int = 0
    retry_at: datetime | None = None
    visited_origins: tuple[str, ...] = ()

    def diagnostics(self):
        return {
            "code": self.code,
            "retryable": self.retryable,
            "httpStatus": self.http_status,
            "redirects": self.redirects,
        }


def is_public(address):
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        return address in GLOBAL_IPV6 and address.sixtofour is None and address.teredo is None
    return True


async def resolve_addresses(host):
    records = await asyncio.get_running_loop().getaddrinfo(
        host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    return tuple(dict.fromkeys(ipaddress.ip_address(record[4][0]) for record in records))


def discoverable_origin(url):
    if url is None or len(url.encode()) > 2048:
        raise MonitoringError(422, "URL_NOT_ALLOWED")
    return origin(url)


def validate_html(sample):
    if not HTML_MARKUP.search(sample):
        return State.NEEDS_REVIEW, "INVALID_HTML"
    try:
        page = html.document_fromstring(sample, parser=html.HTMLParser(no_network=True))
    except (etree.ParserError, ValueError):
        return State.NEEDS_REVIEW, "INVALID_HTML"
    capital = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lower = capital.lower()
    if page.xpath(f"//meta[translate(@http-equiv, '{capital}', '{lower}')='refresh']"):
        return State.NEEDS_REVIEW, "HTML_REDIRECT_REQUIRES_REVIEW"
    if page.xpath(f"//input[translate(@type, '{capital}', '{lower}')='password']"):
        return State.NEEDS_REVIEW, "AUTHENTICATION_REQUIRED"
    visible = page.xpath(
        "//body//text()[not(ancestor::script or ancestor::style or ancestor::template "
        "or ancestor::noscript or ancestor::*[@hidden])]"
    )
    if not any(value.strip() for value in visible):
        return State.NEEDS_REVIEW, "RENDERED_VALIDATION_REQUIRED"
    return State.ACTIVE, "HTML_VALIDATED"


def retry_after(value):
    if not value:
        return None
    now = utc_now()
    try:
        if value.isascii() and value.isdecimal():
            return now + timedelta(seconds=min(int(value[:10]), 3600))
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return min(when, now + timedelta(hours=1))
    except (TypeError, ValueError, OverflowError):
        return None


async def sample_html(response):
    sample = bytearray()
    async for block in response.aiter_raw():
        sample.extend(block[: MAX_SAMPLE_BYTES - len(sample)])
        if len(sample) == MAX_SAMPLE_BYTES:
            break
    return bytes(sample)


async def probe_response(response, redirects, visited):
    status = response.status_code
    if status in {401, 403, 407}:
        state, code = State.NEEDS_REVIEW, "ACCESS_RESTRICTED"
    elif status in {404, 410}:
        state, code = State.FAILED, "HTTP_NOT_FOUND"
    elif status in {408, 425, 429} or 500 <= status <= 599:
        return ProbeResult(
            State.FAILED,
            "HTTP_RETRYABLE",
            True,
            status,
            redirects,
            retry_at=retry_after(response.headers.get("retry-after")),
        )
    elif status != 200:
        state, code = State.NEEDS_REVIEW, "UNEXPECTED_HTTP_STATUS"
    elif (
        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        not in HTML_MEDIA_TYPES
    ):
        state, code = State.NEEDS_REVIEW, "UNSUPPORTED_MEDIA_TYPE"
    elif response.headers.get("content-encoding", "identity").lower() != "identity":
        state, code = State.NEEDS_REVIEW, "UNSUPPORTED_CONTENT_ENCODING"
    else:
        state, code = validate_html(await sample_html(response))
    return ProbeResult(
        state, code, http_status=status, redirects=redirects, visited_origins=tuple(visited)
    )


async def request_html(url, allowed_origins, transport, reserve, timeout):
    visited = set()
    for redirects in range(MAX_REDIRECTS + 1):
        try:
            site = discoverable_origin(url)
            request_url = httpx.URL(url)
        except (MonitoringError, httpx.InvalidURL, ValueError):
            return ProbeResult(
                State.NEEDS_REVIEW,
                "UNSAFE_REDIRECT" if redirects else "URL_NOT_ALLOWED",
                redirects=redirects,
            )
        hostname = site.removeprefix("https://")
        if site not in allowed_origins or request_url.raw_host != hostname.encode("ascii"):
            return ProbeResult(State.NEEDS_REVIEW, "ORIGIN_NOT_APPROVED", redirects=redirects)
        # Resolve every hop. Reject a mixed answer and dial a checked numeric
        # address, so the transport cannot resolve the hostname a second time.
        addresses = await resolve_addresses(hostname)
        if not addresses:
            return ProbeResult(State.FAILED, "DNS_LOOKUP_FAILED", True, redirects=redirects)
        if any(not is_public(address) for address in addresses):
            return ProbeResult(State.NEEDS_REVIEW, "NON_PUBLIC_ADDRESS", redirects=redirects)
        if site not in visited:
            if retry_at := await reserve(site):
                return ProbeResult(
                    State.DISCOVERING, "ORIGIN_THROTTLED", redirects=redirects, retry_at=retry_at
                )
            visited.add(site)
        request = httpx.Request(
            "GET",
            request_url.copy_with(host=str(addresses[0]), fragment=None),
            headers={
                "Host": hostname,
                "Accept": "text/html, application/xhtml+xml",
                "Accept-Encoding": "identity",
            },
            extensions={"sni_hostname": hostname, "timeout": httpx.Timeout(timeout).as_dict()},
        )
        response = await transport.handle_async_request(request)
        try:
            if response.status_code not in {301, 302, 303, 307, 308}:
                return await probe_response(response, redirects, visited)
            if redirects == MAX_REDIRECTS:
                return ProbeResult(State.NEEDS_REVIEW, "TOO_MANY_REDIRECTS", redirects=redirects)
            location = response.headers.get("location")
            if not location:
                return ProbeResult(
                    State.NEEDS_REVIEW, "REDIRECT_WITHOUT_LOCATION", redirects=redirects
                )
            try:
                url = urljoin(url, location)
            except ValueError:
                return ProbeResult(State.NEEDS_REVIEW, "UNSAFE_REDIRECT", redirects=redirects + 1)
        finally:
            await response.aclose()
    raise AssertionError("Redirect limit was not enforced")


async def probe_html(url, policy, reserve, timeout, *, transport=None):
    transport = transport or httpx.AsyncHTTPTransport(
        trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)
    )
    try:
        async with asyncio.timeout(timeout), transport:
            return await request_html(
                url,
                set(policy.origins) | set(policy.additional_origins),
                transport,
                reserve,
                timeout,
            )
    except (TimeoutError, httpx.TimeoutException):
        return ProbeResult(State.FAILED, "HTTP_TIMEOUT", True)
    except socket.gaierror:
        return ProbeResult(State.FAILED, "DNS_LOOKUP_FAILED", True)
    except httpx.TransportError as error:
        cause = error
        while cause is not None:
            if isinstance(cause, ssl.SSLError):
                return ProbeResult(State.NEEDS_REVIEW, "TLS_VALIDATION_FAILED")
            cause = cause.__cause__
        return ProbeResult(State.FAILED, "NETWORK_ERROR", True)
