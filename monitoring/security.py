"""Authorization and navigation rules for explicitly approved sources."""

import hashlib
import json
import re
import secrets
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import select

from monitoring.models import MonitoringAgent

HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
LOCAL_SUFFIXES = {"localhost", "local", "internal", "lan", "home", "test", "invalid", "onion"}
SECRET_KEY = re.compile(
    r"token|password|passwd|secret|session|credential|auth|signature|code$", re.I
)


class MonitoringError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def fingerprint(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def origin(url: str, *, allow_http: bool = False) -> str:
    """Named public origins on the scheme’s ordinary port."""
    try:
        if any(ord(char) <= 32 or ord(char) == 127 or char == chr(92) for char in url):
            raise ValueError
        parsed = urlsplit(url)
        host = (parsed.hostname or "").encode("idna").decode("ascii")
        labels = host.split(".")
        scheme = parsed.scheme
        default_port = 443 if scheme == "https" else 80
        if (
            (scheme != "https" and not (allow_http and scheme == "http"))
            or parsed.port not in (None, default_port)
            or parsed.username is not None
            or len(labels) < 2
            or not all(HOST.fullmatch(label) for label in labels)
            or labels[-1] in LOCAL_SUFFIXES
            or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1])
            or host.endswith(".home.arpa")
            or any(
                SECRET_KEY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
            )
            or any(
                SECRET_KEY.search(key)
                for key, _ in parse_qsl(parsed.fragment, keep_blank_values=True)
            )
        ):
            raise ValueError
    except (ValueError, UnicodeError) as error:
        raise MonitoringError(422, "URL_NOT_ALLOWED") from error
    return f"{scheme}://{host}"


def approve_origins(url, additional):
    approved = {origin(url)}
    for item in additional:
        site = origin(item)
        parts = urlsplit(item)
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise MonitoringError(422, "EXPECTED_HTTPS_ORIGIN")
        approved.add(site)
    return sorted(approved)


def check_origin(url, origins):
    if origin(url) not in origins:
        raise MonitoringError(422, "URL_NOT_APPROVED")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def authorize_admin(offered, configured):
    if not configured:
        raise MonitoringError(503, "ENROLLMENT_DISABLED")
    if not secrets.compare_digest(offered.encode(), configured.encode()):
        raise MonitoringError(401, "INVALID_OPERATOR_TOKEN")


async def authenticate_agent(session, token) -> MonitoringAgent:
    agent = await session.scalar(
        select(MonitoringAgent)
        .where(MonitoringAgent.token_digest == token_digest(token))
        .with_for_update()
    )
    if agent is None or not agent.enabled:
        raise MonitoringError(401, "INVALID_AGENT_TOKEN")
    return agent
