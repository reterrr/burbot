"""Workspace-local authorization for the existing Sources catalogue."""

import re
from urllib.parse import urlsplit

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from extension_sync.identity import reject
from extension_sync.models import SyncSourceGrant, SyncWorkspace
from monitoring.security import MonitoringError, origin
from sources.exceptions import SourceConflict
from sources.schemas.api import SourceCreateRequest, SourceURL
from sources.schemas.enums import SourceState
from sources.schemas.models import Source
from sources.services.sources import SourcesService

source_url = TypeAdapter(SourceURL)
UNAVAILABLE = {SourceState.ARCHIVED, SourceState.BLOCKED_BY_POLICY}


def canonical_source(url):
    # Check the supplied URL before removing fragments or normalizing credentials.
    if re.search(r"%(?![a-fA-F0-9]{2})", url):
        raise ValueError("Malformed source URL escape")
    origin(url, allow_http=True)
    canonical = str(source_url.validate_python(url))
    return canonical, origin(canonical, allow_http=True)


async def workspace_for_admin(session, workspace_id):
    workspace = await session.get(SyncWorkspace, workspace_id, with_for_update=True)
    if workspace is None:
        raise ValueError("Unknown workspace")
    return workspace


async def set_policy(session, workspace_id, origins, *, create, grant_existing):
    sites = set()
    for url in origins:
        try:
            _, site = canonical_source(url)
            parts = urlsplit(url)
            if parts.path not in ("", "/") or parts.query or parts.fragment:
                raise ValueError
        except (MonitoringError, ValidationError, ValueError) as error:
            raise ValueError("Expected an exact public HTTP(S) origin") from error
        sites.add(site)
    if (create or grant_existing) and not sites:
        raise ValueError("Source creation or grants require at least one allowed origin")
    workspace = await workspace_for_admin(session, workspace_id)
    workspace.source_policy = (
        {
            "origins": sorted(sites),
            "create": create,
            "grant_existing": grant_existing,
        }
        if sites
        else {}
    )
    return {"workspaceUuid": str(workspace.id), "sourcePolicy": workspace.source_policy}


async def change_grant(session, workspace_id, source_id, *, revoke):
    workspace = await workspace_for_admin(session, workspace_id)
    grant = await session.get(SyncSourceGrant, (workspace.id, source_id))
    if revoke:
        if grant is not None:
            await session.delete(grant)
    elif grant is None:
        source = await session.get(Source, source_id, with_for_update=True)
        if source is None or source.state in UNAVAILABLE:
            raise ValueError("Source unavailable")
        session.add(SyncSourceGrant(workspace_id=workspace.id, source_id=source.id))
    return {"workspaceUuid": str(workspace.id), "sourceId": str(source_id), "granted": not revoke}


class SourceReconciliation:
    def __init__(self, session, workspace):
        self.session = session
        self.workspace = workspace
        self.sources = SourcesService(session, commit=False)

    async def resolve(self, request, *, apply):
        keys = [entry.client_key for entry in request.sources]
        if len(set(keys)) != len(keys):
            reject(422, "DUPLICATE_SOURCE_CLIENT_KEY")
        normalized = {}
        results = {}
        for entry in request.sources:
            try:
                normalized[entry.client_key] = (*canonical_source(entry.url), entry)
            except (MonitoringError, ValidationError, ValueError):
                results[entry.client_key] = {
                    "clientKey": entry.client_key,
                    "status": "SOURCE_URL_INVALID",
                }
        # Deterministic order for transactions that touch overlapping Source rows.
        for url, site, entry in sorted(normalized.values(), key=lambda item: item[0]):
            results[entry.client_key] = await self.item(entry, url, site, apply=apply)
        return {"items": [results[key] for key in keys]}

    async def item(self, entry, url, site, *, apply, raced=False):
        result = {
            "clientKey": entry.client_key,
            "canonicalUrl": url,
            "type": entry.type.value,
        }
        policy = self.workspace.source_policy
        allowed = site in policy.get("origins", [])
        if allowed:
            source = await self.sources.find_by_url(url, lock=apply)
            grant = source is not None and await self.session.get(
                SyncSourceGrant,
                (self.workspace.id, source.id),
            )
        else:
            query = (
                select(Source)
                .join(SyncSourceGrant, SyncSourceGrant.source_id == Source.id)
                .where(Source.url == url, SyncSourceGrant.workspace_id == self.workspace.id)
            )
            source = await self.session.scalar(query.with_for_update(of=Source) if apply else query)
            if source is None:
                return {**result, "status": "SOURCE_ORIGIN_DENIED"}
            grant = True
        if (
            apply
            and entry.expected_source_id is not None
            and (source is None or str(source.id) != entry.expected_source_id)
        ):
            return {**result, "status": "SOURCE_CHANGED"}
        if source is not None:
            if source.type != entry.type:
                return {**result, "status": "SOURCE_TYPE_MISMATCH", "actualType": source.type}
            if source.state in UNAVAILABLE:
                return {**result, "status": "SOURCE_UNAVAILABLE", "sourceState": source.state}
            confirmed = {**result, "sourceId": str(source.id)}
            if grant:
                return {
                    **confirmed,
                    "status": "RESOLVED" if apply else "EXISTING_SOURCE",
                    "requiresGrant": False,
                }
            can_grant = allowed and bool(policy.get("grant_existing"))
            if can_grant and apply and entry.allow_grant_existing:
                self.session.add(
                    SyncSourceGrant(workspace_id=self.workspace.id, source_id=source.id)
                )
                await self.session.flush()
                return {**confirmed, "status": "RESOLVED", "requiresGrant": False}
            return {
                **confirmed,
                "status": "SOURCE_GRANT_REQUIRED",
                "requiresGrant": True,
                "canGrantExisting": can_grant,
            }
        may_create = allowed and bool(policy.get("create"))
        if not (apply and entry.allow_create and may_create):
            return {**result, "status": "SOURCE_MISSING", "canCreate": may_create}
        try:
            created = await self.sources.create_source(
                SourceCreateRequest(type=entry.type, url=url)
            )
        except SourceConflict:
            # A different workspace or the general Sources API won the unique URL.
            # Re-check the actual row and the grant policy before returning a binding.
            if raced or await self.sources.find_by_url(url) is None:
                raise
            return await self.item(entry, url, site, apply=apply, raced=True)
        self.session.add(SyncSourceGrant(workspace_id=self.workspace.id, source_id=created.id))
        await self.session.flush()
        return {**result, "sourceId": str(created.id), "status": "RESOLVED", "requiresGrant": False}
