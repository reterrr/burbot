"""Connection, display, and service-only lookups shared by the walkthrough."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from business_layer.services import BusinessService

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_KEY = "business_service_demo"


def serialize(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (date, datetime, UUID)):
        return str(value)
    raise TypeError(f"Cannot display {type(value).__name__}")


async def find_model(business, key):
    offset = 0
    while True:
        models, total = await business.entities.get_models(offset=offset, limit=100)
        for model in models:
            if model.key == key:
                return model
        offset += len(models)
        if not models or offset >= total:
            return None


async def demo_model(business, key):
    model = await find_model(business, key)
    if model is None:
        raise RuntimeError("Run step_01_create_model first with the same --model-key")
    if not (model.metadata_json or {}).get("script_demo"):
        raise RuntimeError("This model is not a walkthrough model; choose a different --model-key")
    return model


async def remember(business, model_id, **changes):
    model = await business.entities.get_model(model_id)
    metadata = {**(model.metadata_json or {}), **changes}
    return await business.entities.update_model(model_id, {"metadata_json": metadata})


def seed_ids(model):
    values = (model.metadata_json or {}).get("seed_objects")
    if not values:
        raise RuntimeError("Run step_04_seed_objects first")
    return values


async def object_fields(business, object_id):
    obj = await business.data.get_object(object_id)
    definition = await business.entities.get_entity(obj.business_entity_id)
    names = {field.field_id: field.key for field in definition.fields}
    return {
        names.get(
            field.business_entity_field_id, f"retired:{field.business_entity_field_id}"
        ): field
        for field in obj.fields
    }


async def expect_error(label, operation, status):
    try:
        await operation
    except HTTPException as error:
        if error.status_code != status:
            raise
        return {"check": label, "status": error.status_code, "detail": error.detail}
    raise RuntimeError(f"Expected {label} to be rejected with status {status}")


def run(operation, *, write=True):
    parser = argparse.ArgumentParser(description=operation.__doc__)
    parser.add_argument("--model-key", default=DEFAULT_MODEL_KEY)
    args = parser.parse_args()
    settings = dotenv_values(ROOT / ".env")
    raw_url = settings.get("HOST_DATABASE_URL")
    if not raw_url:
        parser.error("Set HOST_DATABASE_URL in the project's .env")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        parser.error("The walkthrough requires PostgreSQL")
    url = url.set(drivername="postgresql+asyncpg")

    async def execute():
        engine = create_async_engine(url, echo=False, hide_parameters=True, pool_pre_ping=True)
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            async with sessions() as session:
                # This commits on successful completion. There is no test cleanup transaction.
                async with session.begin():
                    result = await operation(BusinessService(session), args.model_key)
            return result
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(execute())
    except (RuntimeError, LookupError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, default=serialize, ensure_ascii=False, indent=2))
    print("COMMITTED — inspect the database now." if write else "READ ONLY — no rows changed.")
