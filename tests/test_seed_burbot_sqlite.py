"""SQLite workspace import against the disposable PostgreSQL migration fixture."""

import hashlib
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from uuid import UUID, uuid4
from zipfile import ZipFile, ZipInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from test_collections_postgres import database as database
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import BusinessObject, BusinessObjectFieldValue
from business_layer.services.data import DataService
from extension_sync.identity import IdentityService
from extension_sync.models import ExternalObjectBinding, SyncReceipt, SyncWorkspace
from extension_sync.schema import DEFINITIONS, bootstrap
from extraction.schemas.models import FieldObservation
from extraction.schemas.selector import Selector, SelectorEvaluation
from extraction.schemas.selector_tree import SelectorTree
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from extraction.services.selectors import SelectorService
from monitoring.models import MonitoringJob, MonitoringSource
from scripts.burbot_sqlite_import import operator_website_list, seed
from scripts.seed_burbot_sqlite import main
from sources.schemas.api import SourceCreateRequest
from sources.schemas.models import Source, SourceBusinessObject, SourceSnapshot, StoredFile
from sources.services.sources import SourcesService

STAMP = "2025-03-10T08:30:00.000Z"
PAGE = "https://example.org/project?a=1&b=2"
PDF = "https://example.org/guide.pdf?download=1"
BLOB = "61bb1928-9061-4b07-8e24-039dfa47eac3"

DDL = """
PRAGMA user_version = 16;
PRAGMA foreign_keys = ON;
CREATE TABLE workspace_state(
  id INTEGER PRIMARY KEY, revision INTEGER, state_json TEXT, updated_at TEXT
);
CREATE TABLE workspace_objects(
  db_id INTEGER PRIMARY KEY, object_id TEXT UNIQUE, object_type TEXT, label TEXT,
  source_url TEXT, created_at TEXT, updated_at TEXT, import_key TEXT, values_json TEXT
);
CREATE TABLE geography_groups(
  id INTEGER PRIMARY KEY, object_id TEXT REFERENCES workspace_objects(object_id)
);
CREATE TABLE projects(
  id INTEGER PRIMARY KEY REFERENCES workspace_objects(db_id), object_id TEXT,
  name TEXT, status TEXT, geography_group_id INTEGER
);
CREATE TABLE operators(
  id INTEGER PRIMARY KEY REFERENCES workspace_objects(db_id), object_id TEXT, name TEXT
);
CREATE TABLE recruitments(
  id INTEGER PRIMARY KEY REFERENCES workspace_objects(db_id), object_id TEXT,
  project_id INTEGER REFERENCES projects(id), operator_id INTEGER REFERENCES operators(id),
  status TEXT, start_low_date TEXT, planned_end_low_month INTEGER, geography_group_id INTEGER
);
CREATE TABLE projects_operators(
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  operator_id INTEGER REFERENCES operators(id), operator_type TEXT
);
CREATE TABLE recruitment_operators(
  id INTEGER PRIMARY KEY, recruitment_id INTEGER REFERENCES recruitments(id),
  operator_id INTEGER REFERENCES operators(id), operator_type TEXT
);
CREATE TABLE operator_contacts(
  contact_id TEXT, object_id TEXT, kind TEXT, variant_no INTEGER, value TEXT
);
CREATE TABLE geographies(
  legacy_id TEXT, object_id TEXT, geography_group_id INTEGER REFERENCES geography_groups(id),
  type TEXT, role TEXT, value TEXT, operator_object_id TEXT, geography_object_id INTEGER
);
CREATE TABLE wojewodztwo_objects(id INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE gmina_objects(id INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE file_sources(
  source_id TEXT, object_id TEXT, file_type TEXT, url TEXT, name TEXT,
  source_page_url TEXT, added_at TEXT
);
CREATE TABLE local_file_blobs(file_id TEXT, name TEXT, mime_type TEXT, size_bytes INTEGER,
                              content BLOB, uploaded_at TEXT);
CREATE TABLE import_sources(source_id TEXT, import_key TEXT, source_type TEXT, url TEXT,
                            snapshot_json TEXT, imported_at TEXT);
CREATE TABLE financing_rules(row_key TEXT, object_id TEXT, position INTEGER, payload_json TEXT);
CREATE TABLE document_requirements(
  row_key TEXT, object_id TEXT, position INTEGER, payload_json TEXT
);
CREATE TABLE selectors(
  uuid TEXT, object_id TEXT, field TEXT, target_json TEXT, source_uuid TEXT,
  page_url TEXT, active_version_uuid TEXT, created_at TEXT, migration_json TEXT, legacy_rule_id TEXT
);
CREATE TABLE selector_versions(uuid TEXT, selector_uuid TEXT, version_no INTEGER, status TEXT,
                               created_from_snapshot_uuid TEXT, artifact_type TEXT, created_at TEXT,
                               reviewed_at TEXT, reviewed_by TEXT);
CREATE TABLE selector_recipes(uuid TEXT, version_uuid TEXT, position INTEGER);
CREATE TABLE selector_parts(uuid TEXT, recipe_uuid TEXT, position INTEGER, extraction_json TEXT,
                            join_with TEXT);
CREATE TABLE selector_locators(
  uuid TEXT, part_uuid TEXT, position INTEGER, kind TEXT, payload_json TEXT
);
CREATE TABLE selector_evaluations(uuid TEXT, version_uuid TEXT, evaluated_at TEXT, page_url TEXT,
                                  result_json TEXT);
"""


class MemoryStorage:
    def __init__(self):
        self.files = {}
        self.calls = []

    def ensure_file(self, key, body, mime, digest):
        self.calls.append(key)
        assert hashlib.sha256(body).hexdigest() == digest
        assert self.files.setdefault(key, (body, mime, digest)) == (body, mime, digest)


def nested(identifier, owner, **fields):
    return {"id": identifier, "objectId": owner, **fields}


def file_body():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as workbook:
        workbook.writestr(ZipInfo("[Content_Types].xml"), "<Types/>")
        workbook.writestr(ZipInfo("xl/workbook.xml"), "<workbook/>")
    return buffer.getvalue()


def insert_tree(db, graph, evaluation=None, *, legacy_rule="rule"):
    header = graph["selector"]
    db.execute(
        "INSERT INTO selectors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            header["uuid"],
            header["target"]["objectId"],
            header["target"]["field"],
            json.dumps(header["target"]),
            header.get("sourceUuid"),
            header["pageUrl"],
            header["activeVersionUuid"],
            header["createdAt"],
            None,
            legacy_rule,
        ),
    )
    for version in graph["versions"]:
        db.execute(
            "INSERT INTO selector_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                version["uuid"],
                header["uuid"],
                version["versionNo"],
                version["status"],
                version["createdFromSnapshotUuid"],
                version["artifactType"],
                version["createdAt"],
                version.get("reviewedAt"),
                version.get("reviewedBy"),
            ),
        )
        for item in version["recipes"]:
            db.execute(
                "INSERT INTO selector_recipes VALUES (?, ?, ?)",
                (
                    item["uuid"],
                    version["uuid"],
                    item["order"],
                ),
            )
            for segment in item["parts"]:
                db.execute(
                    "INSERT INTO selector_parts VALUES (?, ?, ?, ?, ?)",
                    (
                        segment["uuid"],
                        item["uuid"],
                        segment["order"],
                        json.dumps(segment["extraction"]),
                        segment.get("joinWith"),
                    ),
                )
                for locator in segment["locators"]:
                    db.execute(
                        "INSERT INTO selector_locators VALUES (?, ?, ?, ?, ?)",
                        (
                            locator["uuid"],
                            segment["uuid"],
                            locator["order"],
                            locator["kind"],
                            json.dumps(
                                {
                                    name: value
                                    for name, value in locator.items()
                                    if name not in {"uuid", "order", "kind"}
                                }
                            ),
                        ),
                    )
    if evaluation is not None:
        db.execute(
            "INSERT INTO selector_evaluations VALUES (?, ?, ?, ?, ?)",
            (
                evaluation["uuid"],
                evaluation["result"]["selectorVersionUuid"],
                evaluation["evaluatedAt"],
                evaluation["pageUrl"],
                json.dumps(evaluation["result"]),
            ),
        )


def make_fixture(path, *, ddl=DDL):
    graph = tree(
        recipe(
            part(css("#amount"), extraction={"type": "attribute", "name": "data-value"}),
            part(css("#amount"), order=1, joinWith=" PLN "),
        )
    )
    header = graph["selector"]
    header["target"] = {
        "objectId": "project",
        "field": "max_amount_pln",
        "target": {"kind": "funding", "id": "funding-1"},
    }
    header["pageUrl"] = PAGE + "#current"
    graph["versions"][0].update(
        createdFromSnapshotUuid=str(uuid4()), reviewedAt=STAMP, reviewedBy="local reviewer"
    )
    draft = tree(recipe(part(css(".proposal"))), status="draft")["versions"][0]
    draft.update(selectorUuid=header["uuid"], versionNo=4)
    graph["versions"].append(draft)
    definition = SelectorTree.model_validate(graph).versions[0]
    result = evaluate_selector_version(
        definition,
        HtmlSelectorRuntime('<b id="amount" data-value="123">A</b>', PAGE),
    )
    evaluation = {
        "uuid": str(uuid4()),
        "evaluatedAt": STAMP,
        "pageUrl": PAGE,
        "result": result.portable(),
    }
    roots = [
        {
            "id": "operator-a",
            "type": "operator",
            "values": {"name": "Operator A", "role": "operator"},
        },
        {
            "id": "operator-b",
            "type": "operator",
            "values": {"name": "Operator B", "role": "PARTNER"},
        },
        {
            "id": "project",
            "type": "project",
            "label": "Project label",
            "createdAt": STAMP,
            "updatedAt": STAMP,
            "sourceUrl": PAGE + "#top",
            "importKey": "project:original",
            "values": {
                "name": "Project",
                "status": "ACTIVE",
                "documents_link_direct": True,
                "start_date": "2025-03-01",
                "last_checked_at": STAMP,
                "operator_id": "operator-a",
            },
        },
        {
            "id": "recruitment",
            "type": "recruitment",
            "values": {
                "external_number": "2025/1",
                "status": "ANNOUNCED",
                "continuous": False,
                "project_id": "project",
            },
        },
        {"id": "legacy-nabor", "type": "nabor", "values": {"title": "Legacy", "amount": 350}},
    ]
    files = [
        nested(
            "file-remote",
            "project",
            fileType="PDF",
            name="guide.pdf",
            url=PDF + "#page=9",
            sourcePageUrl=PAGE,
            addedAt=STAMP,
            importKey="file:guide",
        ),
        nested(
            "file-local",
            "project",
            fileType="XLSX",
            name="annex.xlsx",
            url=f"http://127.0.0.1:9876/files/{BLOB}/annex.xlsx",
            sourcePageUrl=PAGE,
            addedAt=STAMP,
            display_name="Annex",
        ),
        nested(
            "file-unsupported",
            "project",
            fileType="DOCX",
            name="template.docx",
            url="https://example.org/template.docx",
            sourcePageUrl=PAGE,
            addedAt=STAMP,
        ),
    ]
    state = {
        "version": 1,
        "revision": 12,
        "objects": roots,
        "rules": [
            nested(
                "rule",
                "project",
                field="max_amount_pln",
                pageUrl=PAGE + "#current",
                selectorTree=graph,
                selectorEvaluations=[evaluation],
            )
        ],
        "operatorAssignments": [
            nested("assignment-a", "project", operatorId="operator-a", operatorType="GLOWNY"),
            nested("assignment-b", "project", operatorId="operator-b", operatorType="DODATKOWY"),
            nested("assignment-c", "recruitment", operatorId="operator-a", operatorType="GLOWNY"),
        ],
        "operatorContacts": [
            nested("contact", "operator-a", kind="EMAIL", variant_no=1, value="ops@example.org")
        ],
        "geographies": [
            nested(
                "geo-project",
                "project",
                type="WOJEWODZTWO",
                role="OBEJMUJE",
                value="Mazowieckie",
                operatorId="operator-a",
            ),
            nested(
                "geo-excluded",
                "project",
                type="GMINA",
                role="WYKLUCZA",
                value="Other",
                operatorId="operator-b",
            ),
            nested(
                "geo-recruitment",
                "recruitment",
                type="WOJEWODZTWO",
                role="OBEJMUJE",
                value="Mazowieckie",
                operatorId="operator-a",
                copiedFromProjectId="project",
                copiedFromGeographyId="geo-project",
                copiedAt=STAMP,
            ),
        ],
        "serviceCategories": [nested("category", "project", label="Training")],
        "financingRules": [
            nested(
                "funding-1",
                "project",
                variant_no=1,
                max_amount_pln="123.45",
                refund_percent_min=60,
                service_category_id="category",
                own_contribution_form="CASH",
                importKey="fund:1",
            ),
            nested(
                "funding-2", "project", variant_no=2, max_amount_pln=987.65, refund_percent_max=85
            ),
        ],
        "fileSources": files,
        "documentRequirements": [
            nested(
                "document",
                "project",
                label="Application",
                purpose="FORM",
                requirement="REQUIRED",
                fulfillment_mode="OPERATOR_TEMPLATE",
                signature_requirement="REQUIRED_FILE",
                original_file_source_id="file-remote",
                source_file_source_ids=["file-local", "file-remote", "file-unsupported"],
            ),
        ],
        "importSources": [
            {
                "id": "source",
                "importKey": "snapshot:original",
                "type": "HTML",
                "url": PAGE,
                "snapshot": {"text": "original browser text", "capturedAt": STAMP},
                "importedAt": STAMP,
            },
        ],
        "importTargetEvidence": [
            nested(
                "proof",
                "project",
                target={"kind": "funding", "id": "funding-1"},
                field="max_amount_pln",
                sourceId="source",
                charStart=0,
                charEnd=8,
                rawValue="123.45",
            ),
        ],
    }
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(ddl)
        db.execute(
            "INSERT INTO workspace_state(id, revision, state_json, updated_at) VALUES (1, ?, ?, ?)",
            (state["revision"], json.dumps(state), STAMP),
        )
        for index, row in enumerate(roots, 11):
            db.execute(
                "INSERT INTO workspace_objects(db_id, object_id, object_type, label, source_url, "
                "created_at, updated_at, import_key, values_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    index,
                    row["id"],
                    row["type"],
                    row.get("label"),
                    row.get("sourceUrl"),
                    row.get("createdAt"),
                    row.get("updatedAt"),
                    row.get("importKey"),
                    json.dumps(row["values"]),
                ),
            )
        db.executemany(
            "INSERT INTO geography_groups VALUES (?, ?)", [(5, "project"), (6, "recruitment")]
        )
        db.executemany(
            "INSERT INTO operators(id, object_id, name) VALUES (?, ?, ?)",
            [(11, "operator-a", "Operator A"), (12, "operator-b", "Operator B")],
        )
        db.execute(
            "INSERT INTO projects(id, object_id, geography_group_id, name, status)"
            " VALUES (13, 'project', 5, 'Project', 'ACTIVE')"
        )
        db.execute("""INSERT INTO recruitments(id, object_id, project_id, operator_id,
                      start_low_date, planned_end_low_month, geography_group_id, status)
                      VALUES (14,'recruitment',13,11,'2025-04-30',7,6,'ANNOUNCED')""")
        db.executemany(
            "INSERT INTO projects_operators VALUES (?, 13, ?, ?)",
            [(19, 11, "GLOWNY"), (20, 12, "DODATKOWY")],
        )
        db.execute("INSERT INTO recruitment_operators VALUES (61,14,11,'GLOWNY')")
        db.execute(
            "INSERT INTO operator_contacts VALUES (?, ?, ?, ?, ?)",
            ("contact", "operator-a", "EMAIL", 1, "ops@example.org"),
        )
        db.execute("INSERT INTO wojewodztwo_objects VALUES (1, 'Mazowieckie')")
        db.execute("INSERT INTO gmina_objects VALUES (1, 'Other')")
        db.executemany(
            "INSERT INTO geographies(legacy_id, object_id, geography_group_id, type, role, "
            "value, operator_object_id, geography_object_id) VALUES (?,?,?,?,?,?,?,1)",
            [
                (
                    g["id"],
                    g["objectId"],
                    5 if g["objectId"] == "project" else 6,
                    g["type"],
                    g["role"],
                    g["value"],
                    g["operatorId"],
                )
                for g in state["geographies"]
            ],
        )
        for file in files:
            db.execute(
                "INSERT INTO file_sources VALUES (?,?,?,?,?,?,?)",
                (
                    file["id"],
                    file["objectId"],
                    file["fileType"],
                    file["url"],
                    file["name"],
                    file["sourcePageUrl"],
                    file["addedAt"],
                ),
            )
        body = file_body()
        db.execute(
            "INSERT INTO local_file_blobs VALUES (?,?,?,?,?,?)",
            (BLOB, "annex.xlsx", None, len(body), body, STAMP),
        )
        source = state["importSources"][0]
        db.execute(
            "INSERT INTO import_sources VALUES (?,?,?,?,?,?)",
            (
                source["id"],
                source["importKey"],
                source["type"],
                source["url"],
                json.dumps(source["snapshot"]),
                source["importedAt"],
            ),
        )
        for table, collection in (
            ("financing_rules", "financingRules"),
            ("document_requirements", "documentRequirements"),
        ):
            for index, row in enumerate(state[collection]):
                db.execute(
                    f"INSERT INTO {table} VALUES (?,?,?,?)",
                    (
                        f"{table}:{index}",
                        row["objectId"],
                        index,
                        json.dumps(row),
                    ),
                )
        insert_tree(db, graph, evaluation)
    return state, graph, evaluation


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path / "workspace.sqlite"
    return path, *make_fixture(path)


async def initialize(factory):
    async with factory.begin() as session:
        await bootstrap(session, apply=True)
        return (
            await SourcesService(session, commit=False).create_source(
                SourceCreateRequest(url=PAGE, type="HTML")
            )
        ).id


async def snapshot(factory, schema):
    models = (
        BusinessObject,
        BusinessObjectFieldValue,
        ExternalObjectBinding,
        SyncWorkspace,
        SyncReceipt,
        Source,
        StoredFile,
        SourceSnapshot,
        SourceBusinessObject,
        Selector,
        SelectorEvaluation,
        FieldObservation,
        MonitoringSource,
        MonitoringJob,
    )
    async with factory() as session:
        counts = {
            model.__name__: await session.scalar(select(func.count()).select_from(model))
            for model in models
        }
        sequences = (
            await session.execute(
                text(
                    "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = :schema"
                ),
                {"schema": schema},
            )
        ).all()
    return counts, dict(sequences)


async def objects(factory, namespace):
    async with factory() as session:
        workspace = await session.get(SyncWorkspace, namespace)
        service = IdentityService(session, workspace)
        registry = await service.registry(await service.model())
        by_entity = {int(entry["businessEntityId"]): entry for entry in registry.values()}
        rows = await session.scalars(
            select(ExternalObjectBinding).where(ExternalObjectBinding.workspace_id == namespace)
        )
        result = {}
        for row in rows:
            key = tuple(json.loads(row.external_object_id))
            obj = await service.data.get_object(row.business_object_id)
            fields = {field.business_entity_field_id: field for field in obj.fields}
            slots = {
                f["persistentKey"]: fields[int(f["businessEntityFieldId"])]
                for f in by_entity[row.business_entity_id]["fields"]
            }
            result[key] = (obj, slots)
        return result


@pytest.mark.asyncio
async def test_import_preserves_records_and_reuses_canonical_ids(database, fixture):
    _, factory, schema = database
    page_id = await initialize(factory)
    path, state, graph, evaluation = fixture
    before = await snapshot(factory, schema)
    original = path.read_bytes()
    namespace, storage = uuid4(), MemoryStorage()

    preview = await seed(factory, path, workspace_uuid=namespace, storage=storage)
    assert preview.exit_code == 0, preview.as_dict()
    assert preview.as_dict()["byInput"]["selectors"] == {"would_import": 1}
    assert preview.as_dict()["byInput"]["sources"] == {"reused": 1, "would_import": 1}
    assert preview.as_dict()["mirrored"]["operator_assignments"] == 3
    assert await snapshot(factory, schema) == before
    assert path.read_bytes() == original and not storage.calls

    report = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert report.exit_code == 0, report.as_dict()
    expected_records = 19
    indexed = await objects(factory, namespace)
    assert len(indexed) == expected_records

    def data(identifier, kind=None, owner=None):
        obj, slots = indexed[owner or identifier, kind, identifier if kind else None]
        return obj.id, {key: field.value for key, field in slots.items() if field.value_id}

    project, project_fields = data("project")
    recruitment, recruitment_fields = data("recruitment")
    operator, _ = data("operator-a")
    assert project_fields["status"] == "AKTYWNY" and project_fields["operator_id"] == operator
    assert project_fields["start_date"] == "2025-03-01" and project_fields["documents_link_direct"]
    assert project_fields["last_checked_at"] == STAMP
    assert indexed["project", None, None][0].created_at == datetime.fromisoformat(STAMP)
    assert (
        recruitment_fields["project_id"] == project
        and recruitment_fields["operator_id"] == operator
    )
    assert recruitment_fields["status"] == "OGLOSZONY" and recruitment_fields["continuous"] is False
    assert recruitment_fields["dataRozpoczeciaOd"] == "2025-04-30"
    assert recruitment_fields["planned_end_low_month"] == 7
    assert data("legacy-nabor")[1]["external_number"] == "Legacy"
    assert data("assignment-b", "operator_assignment", "project")[1]["operatorType"] == "DODATKOWY"
    assert (
        data("assignment-c", "operator_assignment", "recruitment")[1]["recruitment_owner"]
        == recruitment
    )
    assert data("contact", "operator_contact", "operator-a")[1]["operator_owner"] == operator
    category, _ = data("category", "service_category", "project")
    _, funding = data("funding-1", "funding", "project")
    assert (funding["max_amount_pln"], funding["service_category_id"]) == ("123.45", category)
    assert data("funding-2", "funding", "project")[1]["max_amount_pln"] == "987.65"
    geo_id, geo = data("geo-project", "geography", "project")
    copy_id, copy = data("geo-recruitment", "geography", "recruitment")
    assert (
        geo_id != copy_id
        and geo["project_owner"] == project
        and copy["recruitment_owner"] == recruitment
    )
    assert geo["operatorId"] == copy["operatorId"] == operator
    assert data("geo-excluded", "geography", "project")[1]["role"] == "WYKLUCZA"
    file_ids = [
        data(identifier, "file_source", "project")[0]
        for identifier in state["documentRequirements"][0]["source_file_source_ids"]
    ]
    assert data("document", "document", "project")[1]["source_file_source_ids"] == file_ids
    _, remote = data("file-remote", "file_source", "project")
    _, local = data("file-local", "file_source", "project")
    assert remote["url"] == PDF + "#page=9"
    assert report.as_dict()["byInput"]["file_sources"]["unsupported"] == 1
    assert report.as_dict()["byInput"]["workspace_state.importTargetEvidence"] == {"pending": 1}

    async with factory() as session:
        source = await session.get(Source, remote["source"])
        assert source.url == PDF and source.type == "PDF"
        source = await session.get(Source, local["source"])
        stored = await session.get(StoredFile, source.file_id)
        assert source.url is None and source.type == "XLSX"
        assert stored.size_bytes == len(file_body())
        assert stored.created_at == datetime.fromisoformat(STAMP)
        assert storage.files[stored.storage_key][0] == file_body()
        receipt_rows = list(await session.scalars(select(SyncReceipt)))
        metadata = {
            row.result["businessObjectId"]: row.result["metadata"]
            for row in receipt_rows
            if "metadata" in row.result
        }
        assert metadata[str(project)]["importKey"] == "project:original"
        assert metadata[str(project)]["geographyGroupId"] == 5
        assert metadata[str(copy_id)]["copiedFromGeographyId"] == "geo-project"
        stored_selector = await SelectorService(session).selector(UUID(graph["selector"]["uuid"]))
        expected_target = indexed["project", "funding", "funding-1"][1]["max_amount_pln"]
        assert stored_selector.business_object_field_id == expected_target.object_field_id
        assert stored_selector.source_id == page_id
        saved, versions = await SelectorService(session).tree(stored_selector)
        assert saved.model_dump() == SelectorTree.model_validate(graph).model_dump()
        assert stored_selector.active_version_id == versions[0].id
        assert versions[0].created_from_snapshot_id is None
        recorded = await session.scalar(select(SelectorEvaluation))
        assert (
            recorded.uuid == UUID(evaluation["uuid"]) and recorded.provenance == "client_reported"
        )
        assert recorded.evaluated_at == datetime.fromisoformat(STAMP)
        assert recorded.source_snapshot_id is None and recorded.extraction_run_id is None
        assert not (await session.get(SyncWorkspace, namespace)).enabled

    after = await snapshot(factory, schema)
    assert after[0]["Source"] == 3 and after[0]["StoredFile"] == 1
    assert after[0]["SourceSnapshot"] == after[0]["FieldObservation"] == 0
    assert after[0]["MonitoringJob"] == after[0]["MonitoringSource"] == 0
    repeated = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert repeated.exit_code == 0, repeated.as_dict()
    assert "imported" not in repeated.as_dict()["summary"]
    assert await snapshot(factory, schema) == after
    assert path.read_bytes() == original and len(storage.files) == 1


@pytest.mark.asyncio
async def test_failed_record_rolls_back_retry_and_conflict(database, fixture, monkeypatch):
    _, factory, schema = database
    await initialize(factory)
    path, _, _, _ = fixture
    namespace, storage = uuid4(), MemoryStorage()
    original = DataService.assign_object_fields_values

    async def fail_project(self, object_id, values, **conditions):
        if "Project" in values.values():
            raise HTTPException(422, "Test failure after creating project and its slots")
        return await original(self, object_id, values, **conditions)

    monkeypatch.setattr(DataService, "assign_object_fields_values", fail_project)
    failed = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert failed.exit_code == 1
    existing = await objects(factory, namespace)
    assert ("operator-a", None, None) in existing
    assert ("project", None, None) not in existing
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(BusinessObject)) == len(
            existing
        )
    monkeypatch.undo()
    repaired = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert repaired.exit_code == 0, repaired.as_dict()
    final = await objects(factory, namespace)
    assert {key: final[key][0].id for key in existing} == {
        key: value[0].id for key, value in existing.items()
    }

    project, slots = final["project", None, None]
    slot = slots["name"]
    async with factory.begin() as session:
        await DataService(session).assign_object_fields_values(
            project.id,
            {slot.object_field_id: "Edited in the backend"},
            expected_value_ids={slot.object_field_id: slot.value_id},
        )
    before = await snapshot(factory, schema)
    for apply in (False, True):
        conflict = await seed(factory, path, apply=apply, workspace_uuid=namespace, storage=storage)
        matching = [
            row for row in conflict.entries if row.get("reason") == "CANONICAL_VALUE_DIFFERS"
        ]
        assert [(row["field"], row["canonicalValue"]) for row in matching] == [
            ("name", "Edited in the backend")
        ]
        assert await snapshot(factory, schema) == before


@pytest.mark.asyncio
async def test_unregistered_and_stale_database_are_blocked(database, fixture):
    _, factory, schema = database
    path, *_ = fixture
    preview = await seed(factory, path, apply=True)
    assert preview.exit_code == 1
    assert any(
        "Register the Burbot business schema" in row.get("reason", "") for row in preview.entries
    )
    assert (await snapshot(factory, schema))[0]["SyncWorkspace"] == 0
    async with factory.begin() as session:
        await session.execute(
            text("UPDATE alembic_version SET version_num = 'known_stale_fixture'")
        )
    report = await seed(factory, path, apply=True)
    assert report.postgresql["alembicRevisions"] == ("known_stale_fixture",)
    assert report.exit_code == 1
    assert (await snapshot(factory, schema))[0]["Source"] == 0


def test_report_cannot_overwrite_sqlite(fixture):
    path, *_ = fixture
    original = path.read_bytes()
    with pytest.raises(SystemExit, match="1"):
        main(["--sqlite-file", str(path), "--report", str(path)])
    assert path.read_bytes() == original


DOCX_BLOB = "1775845a-52e5-4b47-9b70-bcae89a6dcbe"
OPERATOR_URLS = "https://one.example/terms;v=1; https://two.example/help?item=a;b=2"


def add_dry_run_regressions(path, *, ddl=DDL):
    state, _, _ = make_fixture(path, ddl=ddl)
    roots = {row["id"]: row for row in state["objects"]}
    roots["operator-a"]["values"]["website"] = OPERATOR_URLS
    roots["operator-b"]["values"]["website"] = "https://SAME.example/; https://same.example"
    other_project = {"id": "other-project", "type": "project", "values": {"name": "Other project"}}
    state["objects"].append(other_project)
    state["serviceCategories"].append(nested("other-category", "other-project", label="Other"))
    funding = nested(
        "inherited-funding",
        "recruitment",
        variant_no=1,
        service_category_id="category",
        max_amount_pln="234.56",
    )
    state["financingRules"].append(funding)

    operator_file = nested(
        "operator-file",
        "operator-a",
        fileType="DOCX",
        name="template.docx",
        url=f"http://127.0.0.1:9876/files/{DOCX_BLOB}/template.docx",
        sourcePageUrl=PAGE,
        addedAt=STAMP,
        importKey="operator-template",
    )
    state["fileSources"].append(operator_file)
    attachment = {
        "id": "captured-operator-file",
        "importKey": "operator-template-capture",
        "type": "DOCX",
        "url": operator_file["url"],
        "snapshot": {"text": "Sample template text"},
        "importedAt": STAMP,
    }
    state["importSources"].append(attachment)
    state["documentRequirements"][0]["document_type_key"] = "msp_application_form"
    state["documentRequirements"][0]["auto_fill"] = False
    legacy_graphs = []
    for owner in ("project", "recruitment"):
        graph = tree()
        graph["selector"]["target"] = {
            "objectId": owner,
            "field": "auto_fill",
            "target": {"kind": "document", "id": "msp_application_form"},
        }
        graph["selector"]["pageUrl"] = PAGE
        legacy_graphs.append(graph)

    with closing(sqlite3.connect(path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "INSERT INTO workspace_objects(db_id, object_id, object_type, values_json) "
            "VALUES (99, ?, ?, ?)",
            (other_project["id"], other_project["type"], json.dumps(other_project["values"])),
        )
        db.execute(
            "INSERT INTO projects(id, object_id, name, status) VALUES "
            "(99, 'other-project', 'Other project', 'PLANOWANY')"
        )
        for identifier in ("operator-a", "operator-b"):
            db.execute(
                "UPDATE workspace_objects SET values_json = ? WHERE object_id = ?",
                (json.dumps(roots[identifier]["values"]), identifier),
            )
        db.execute(
            "INSERT INTO financing_rules VALUES (?, ?, ?, ?)",
            ("funding:inherited", funding["objectId"], 9, json.dumps(funding)),
        )
        db.execute(
            "UPDATE document_requirements SET payload_json = ? WHERE row_key = ?",
            (json.dumps(state["documentRequirements"][0]), "document_requirements:0"),
        )
        db.execute(
            "INSERT INTO file_sources VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                operator_file["id"],
                operator_file["objectId"],
                operator_file["fileType"],
                operator_file["url"],
                operator_file["name"],
                PAGE,
                STAMP,
            ),
        )
        db.execute(
            "INSERT INTO import_sources VALUES (?, ?, ?, ?, ?, ?)",
            (
                attachment["id"],
                attachment["importKey"],
                attachment["type"],
                attachment["url"],
                json.dumps(attachment["snapshot"]),
                STAMP,
            ),
        )
        for file_id, name, mime, body in report_fixture_blobs():
            db.execute(
                "INSERT INTO local_file_blobs VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, name, mime, len(body), body, STAMP),
            )
        for graph in legacy_graphs:
            insert_tree(db, graph, legacy_rule=None)
        db.execute("UPDATE workspace_state SET state_json = ? WHERE id = 1", (json.dumps(state),))
    return state, legacy_graphs


def report_fixture_blobs():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(ZipInfo("[Content_Types].xml"), "<Types/>")
        archive.writestr(ZipInfo("word/document.xml"), "<document/>")
    return (
        (
            DOCX_BLOB,
            "template.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            buffer.getvalue(),
        ),
        (
            "c9331984-a243-4a23-a646-b4e30de99006",
            "legacy.doc",
            "application/msword",
            b"\xd0\xcf\x11\xe0 Example Word document",
        ),
        ("5028f78a-c6eb-4556-bab4-0a10d72f1687", "archive.zip", "application/zip", file_body()),
    )


def outcome(report, reason):
    return [record for record in report.entries if record.get("reason") == reason]


@pytest.mark.asyncio
async def test_dry_run_report_regressions(database, tmp_path, monkeypatch):
    _, factory, schema = database
    path = tmp_path / "report-fixture.sqlite"
    _, (resolved, unresolved) = add_dry_run_regressions(path)
    file_definition = DEFINITIONS["file_source"]
    with monkeypatch.context() as original:
        original.setitem(
            DEFINITIONS,
            "file_source",
            {
                **file_definition,
                "fields": [f for f in file_definition["fields"] if f["key"] != "operator_owner"],
                "parents": ["project", "recruitment"],
            },
        )
        await initialize(factory)

    storage, namespace = MemoryStorage(), uuid4()
    before = await snapshot(factory, schema)
    input_bytes = path.read_bytes()
    preview = await seed(factory, path, workspace_uuid=namespace, storage=storage)
    assert preview.exit_code == 0, preview.as_dict()["summary"]
    pending = outcome(preview, "OPERATOR_FILE_OWNER_FIELD_UNREGISTERED")
    assert [record["localObjectId"] for record in pending] == ["operator-a"]
    assert pending[0]["storedFile"]["localFileId"] == DOCX_BLOB
    assert await snapshot(factory, schema) == before
    assert not storage.calls

    async with factory.begin() as session:
        schema_preview = await bootstrap(session)
        assert schema_preview["changes"]
        await bootstrap(session, apply=True, expected_revision=int(schema_preview["revisionId"]))

    preview = await seed(factory, path, workspace_uuid=namespace, storage=storage)
    assert preview.exit_code == 0, preview.as_dict()["summary"]
    assert not outcome(preview, "OPERATOR_FILE_OWNER_FIELD_UNREGISTERED")
    assert preview.as_dict()["byInput"]["stored_files"] == {"would_import": 4}
    pending = outcome(preview, "LEGACY_DOCUMENT_TARGET_UNRESOLVED")
    assert [record["payload"] for record in pending] == [unresolved]

    applied = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert applied.exit_code == 0, applied.as_dict()["summary"]
    indexed = await objects(factory, namespace)
    project_category, _ = indexed["project", "service_category", "category"]
    _, funding = indexed["recruitment", "funding", "inherited-funding"]
    assert funding["service_category_id"].value == project_category.id
    assert sum(key[1] == "service_category" for key in indexed) == 2
    operator, website = indexed["operator-a", None, None]
    assert website["website"].value_id is None
    assert indexed["operator-b", None, None][1]["website"].value == "https://SAME.example/"
    file_object, file_slots = indexed["operator-a", "file_source", "operator-file"]
    assert file_slots["operator_owner"].value == operator.id
    assert (
        file_slots["project_owner"].value is None and file_slots["recruitment_owner"].value is None
    )
    assert file_slots["source"].value is None
    document, document_slots = indexed["project", "document", "document"]
    assert document_slots["document_type_key"].value == "msp_application_form"

    async with factory() as session:
        receipt_rows = list(await session.scalars(select(SyncReceipt)))
        original = next(
            row.result["operatorWebsite"]
            for row in receipt_rows
            if row.result.get("businessObjectId") == str(operator.id)
            and "operatorWebsite" in row.result
        )
        assert original == {
            "original": OPERATOR_URLS,
            "urls": OPERATOR_URLS.split("; https://")[0:1]
            + ["https://two.example/help?item=a;b=2"],
            "primary": None,
        }
        receipt = next(
            row.result
            for row in receipt_rows
            if row.result.get("businessObjectId") == str(file_object.id)
            and "storedFile" in row.result
        )
        assert receipt["storedFile"]["localFileId"] == DOCX_BLOB
        for file_id, _, mime, body in report_fixture_blobs():
            entries = [
                row
                for row in applied.entries
                if row["input"] == "stored_files" and row["localId"] == file_id
            ]
            assert len(entries) == 1 and entries[0]["status"] == "imported"
            stored = await session.get(StoredFile, int(entries[0]["storedFileId"]))
            assert stored.mime_type == mime and storage.files[stored.storage_key][0] == body
            assert await session.scalar(select(Source).where(Source.file_id == stored.id)) is None
        legacy_selector = await SelectorService(session).selector(
            UUID(resolved["selector"]["uuid"])
        )
        saved, _ = await SelectorService(session).tree(legacy_selector)
        assert saved.portable() == SelectorTree.model_validate(resolved).portable()
        assert (
            legacy_selector.business_object_field_id == document_slots["auto_fill"].object_field_id
        )
        assert (
            await SelectorService(session).selector(
                UUID(unresolved["selector"]["uuid"]),
                required=False,
            )
            is None
        )
        assert document.id != file_object.id

    preserved_count, pending_count = (3, 1)
    assert (
        sum(
            row["input"] == "local_file_blobs"
            for row in outcome(applied, "UNSUPPORTED_DOCUMENT_FORMAT")
        )
        == preserved_count
    )
    assert len(outcome(applied, "FILE_BYTES_NOT_IN_SQLITE")) == pending_count
    after = await snapshot(factory, schema)
    repeat = await seed(factory, path, apply=True, workspace_uuid=namespace, storage=storage)
    assert repeat.exit_code == 0 and "imported" not in repeat.as_dict()["summary"]
    assert await snapshot(factory, schema) == after
    assert path.read_bytes() == input_bytes

    # A change to the canonical parent cannot authorize the same SQLite category again.
    recruitment, slots = indexed["recruitment", None, None]
    other, _ = indexed["other-project", None, None]
    slot = slots["project_id"]
    async with factory.begin() as session:
        await DataService(session).assign_object_fields_values(
            recruitment.id,
            {slot.object_field_id: other.id},
            expected_value_ids={slot.object_field_id: slot.value_id},
        )
    conflict = await seed(factory, path, workspace_uuid=namespace, storage=storage)
    assert "project_id" in {row["field"] for row in outcome(conflict, "CANONICAL_VALUE_DIFFERS")}
    assert [
        row["localId"]
        for row in outcome(
            conflict,
            "service_category_id: UNRESOLVED_SERVICE_CATEGORY_REFERENCE",
        )
    ] == ["inherited-funding"]


def test_operator_website_parsing_preserves_semicolons_in_url_components():
    assert operator_website_list("https://example.org/page;format=small") is None
    assert (
        operator_website_list("https://example.org/?urls=https://a.example;https://b.example")
        is None
    )
    assert operator_website_list("https://a.example/p;https://b.example/")["primary"] is None
    assert (
        operator_website_list("https://a.example; https://a.example/")["primary"]
        == "https://a.example"
    )
