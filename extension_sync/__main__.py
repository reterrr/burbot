"""Operator entry point for schema bootstrap and namespace enrollment."""

import argparse
import asyncio
import json
from uuid import UUID

from fastapi import HTTPException

from extension_sync.identity import provision
from extension_sync.models import SyncWorkspace
from extension_sync.schema import bootstrap
from shared.database import session_factory


async def run(args):
    async with session_factory.begin() as session:
        if args.command == "bootstrap":
            return await bootstrap(
                session, apply=args.apply, expected_revision=args.expected_revision
            )
        if args.command == "revoke":
            workspace = await session.get(SyncWorkspace, args.workspace, with_for_update=True)
            if workspace is None:
                raise ValueError("Unknown workspace")
            workspace.enabled = False
            return {"workspaceUuid": str(workspace.id), "enabled": False}
        token = await provision(
            session,
            args.workspace,
            can_create=args.create,
            can_bind_existing=args.bind_existing,
            can_commit=args.commit,
            source_ids=args.source,
            rotate=args.rotate,
        )
        return {"workspaceUuid": str(args.workspace), "workspaceToken": token}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    schema = commands.add_parser("bootstrap")
    schema.add_argument("--apply", action="store_true")
    schema.add_argument("--expected-revision", type=int)
    grant = commands.add_parser("provision")
    grant.add_argument("workspace", type=UUID)
    grant.add_argument("--create", action="store_true")
    grant.add_argument("--bind-existing", action="store_true")
    grant.add_argument("--commit", action="store_true")
    grant.add_argument("--rotate", action="store_true")
    grant.add_argument("--source", action="append", type=int, default=[])
    revoke = commands.add_parser("revoke")
    revoke.add_argument("workspace", type=UUID)
    try:
        result = asyncio.run(run(parser.parse_args()))
    except HTTPException as error:
        parser.exit(1, json.dumps(error.detail, ensure_ascii=False) + "\n")
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
