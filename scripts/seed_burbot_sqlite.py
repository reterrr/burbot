#!/usr/bin/env python3
"""Seed an existing Burbot PostgreSQL schema from a Firefox SQLite backup."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.burbot_sqlite_import import seed
from scripts.burbot_sqlite_input import Report
from scripts.burbot_sqlite_sources import S3Files


async def run(args):
    report = Report(apply=args.apply)
    try:
        from shared.database import engine, session_factory
    except (KeyError, ValueError):
        report.add("failed", "postgresql", reason="Configure the backend DCKR_DATABASE_URL")
        return report
    from monitoring.security import MonitoringError
    from monitoring.storage import storage_from_env

    storage = None
    try:
        storage = S3Files(storage_from_env())
    except (ImportError, ValueError):
        pass
    except MonitoringError as error:
        if error.code != "STORAGE_NOT_CONFIGURED":
            raise
    try:
        return await seed(
            session_factory,
            args.sqlite_file,
            apply=args.apply,
            workspace_uuid=args.workspace_uuid,
            storage=storage,
            report=report,
        )
    finally:
        await engine.dispose()


def write_report(args):
    if args.report is None:
        report = asyncio.run(run(args))
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=True, allow_nan=False))
        return report.exit_code

    destination = args.report.absolute()
    source = args.sqlite_file.resolve()
    if destination.resolve() in {source, Path(f"{source}-wal"), Path(f"{source}-shm")} or (
        destination.exists() and source.exists() and destination.samefile(source)
    ):
        raise ValueError("The report path overlaps the SQLite input")
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        delete=False,
        prefix=f".{destination.name}.",
    ) as stream:
        temporary = Path(stream.name)
        try:
            report = asyncio.run(run(args))
            result = report.as_dict()
            json.dump(result, stream, indent=2, ensure_ascii=True, allow_nan=False)
            stream.write("\n")
            stream.close()
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    print(
        json.dumps({"mode": report.mode, "report": str(destination), "summary": result["summary"]})
    )
    return report.exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-file", required=True, type=Path, help="Firefox SQLite backup")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Inspect and validate (default)")
    mode.add_argument("--apply", action="store_true", help="Commit the reviewed import")
    parser.add_argument("--report", type=Path, help="Write a detailed JSON report")
    parser.add_argument(
        "--workspace-uuid", type=UUID, help="Namespace for an older SQLite workspace"
    )
    try:
        return write_report(parser.parse_args(argv))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    sys.exit(main())
