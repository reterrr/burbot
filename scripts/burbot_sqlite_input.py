"""Read the Firefox workspace and reconcile its SQLite projections."""

import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from extension_sync.schema import ALIASES, DEFINITIONS, local_type

ROOT_TABLES = {"operator": "operators", "project": "projects", "recruitment": "recruitments"}
NESTED = {
    "operator_assignment": "operatorAssignments",
    "operator_contact": "operatorContacts",
    "geography": "geographies",
    "service_category": "serviceCategories",
    "funding": "financingRules",
    "file_source": "fileSources",
    "document": "documentRequirements",
}
RECRUITMENT_COLUMNS = {
    "start_low_date": "dataRozpoczeciaOd",
    "start_ceil_date": "dataRozpoczeciaDo",
    "end_low_date": "dataZakonczeniaOd",
    "end_ceil_date": "dataZakonczeniaDo",
    "start_time": "godzinaRozpoczecia",
    "end_time": "godzinaZakonczenia",
    "closed_status": "statusZakonczenia",
    "status_reason": "powodStatusu",
    "announcement_url": "urlOgloszenia",
    "planned_start_year": "planowanyStartRok",
    "planned_start_month": "planowanyStartMiesiac",
    "planned_start_week": "planowanyStartTydzien",
    "planned_start_quarter": "planowanyStartKwartal",
    "planned_end_year": "planowanyKoniecRok",
    "planned_end_month": "planowanyKoniecMiesiac",
    "planned_end_week": "planowanyKoniecTydzien",
    "planned_end_quarter": "planowanyKoniecKwartal",
}
OBJECT_COLUMNS = {
    "label": "label",
    "source_url": "sourceUrl",
    "creation_note": "creationNote",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
    "import_key": "importKey",
    "evidence_json": "evidence",
    "manual_fields_json": "manualFields",
}
GEOGRAPHY_DICTIONARIES = {
    "POLSKA": "polska_objects",
    "WOJEWODZTWO": "wojewodztwo_objects",
    "PODREGION": "podregion_objects",
    "POWIAT": "powiat_objects",
    "GMINA": "gmina_objects",
    "MIASTO_NA_PRAWACH_POWIATU": "miasto_na_prawach_powiatu_objects",
}


def reject_constant(value):
    raise ValueError(f"Invalid JSON constant {value}")


def json_object(value):
    result = json.loads(value, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("Expected an original timestamp with its timezone offset")
    return result


@contextmanager
def open_sqlite(path: Path):
    uri = path.resolve(strict=True).as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only = ON")
        db.execute("PRAGMA trusted_schema = OFF")
        db.execute("BEGIN")
        yield db


class Report:
    def __init__(self, *, apply):
        self.mode = "apply" if apply else "dry-run"
        self.sqlite = {}
        self.postgresql = {}
        self.mirrored = Counter()
        self.entries = []

    def add(self, status, table, local_id=None, reason=None, **detail):
        entry = {"status": status, "input": table}
        if local_id is not None:
            entry["localId"] = local_id
        if reason is not None:
            entry["reason"] = reason
        self.entries.append({**entry, **detail})

    def as_dict(self):
        counts = Counter(row["status"] for row in self.entries)
        by_input = defaultdict(Counter)
        for row in self.entries:
            by_input[row["input"]][row["status"]] += 1
        return {
            "format": 1,
            "mode": self.mode,
            "sqlite": self.sqlite,
            "postgresql": self.postgresql,
            "summary": dict(counts),
            "byInput": dict(by_input),
            "mirrored": dict(self.mirrored),
            "records": self.entries,
        }

    @property
    def exit_code(self):
        return int(any(row["status"] in {"failed", "conflict"} for row in self.entries))


@dataclass
class LocalObject:
    table: str
    owner: str
    root_type: str
    payload: dict
    values: dict
    kind: str | None = None
    local_id: str | None = None

    @property
    def key(self):
        return self.owner, self.kind, self.local_id

    @property
    def entity_type(self):
        return self.kind or local_type(self.root_type)

    @property
    def ref(self):
        return self.local_id or self.owner


@dataclass
class Workspace:
    db: sqlite3.Connection
    report: Report
    tables: set[str] = field(default_factory=set)
    state: dict = field(default_factory=dict)
    workspace_uuid: UUID | None = None
    objects: dict[tuple, LocalObject] = field(default_factory=dict)
    blobs: dict[str, dict] = field(default_factory=dict)
    imports: dict[str, dict] = field(default_factory=dict)
    trees: dict[str, dict] = field(default_factory=dict)
    tree_rule_ids: dict[str, str] = field(default_factory=dict)
    rules: dict[str, dict] = field(default_factory=dict)
    evaluations: dict[str, dict] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)
    target_evidence: dict[str, dict] = field(default_factory=dict)

    def rows(self, table):
        if table not in self.tables:
            return []
        # Identifiers are quoted, including names discovered via SQLite introspection.
        quoted = '"' + table.replace('"', '""') + '"'
        return [dict(row) for row in self.db.execute(f"SELECT * FROM {quoted}")]

    def collection(self, name):
        rows = self.state.get(name, [])
        if not isinstance(rows, list):
            raise ValueError(f"workspace_state.{name} must be an array")
        return rows

    def merged(self, table, collection, normalized, *, key="id"):
        result = self.index(table, normalized, key=key)
        state_name = f"workspace_state.{collection}"
        for identifier, row in self.index(state_name, self.collection(collection), key=key).items():
            projected = result.get(identifier)
            if projected is not None:
                self.report.mirrored[table] += 1
                differences = {
                    name: {"sqlite": value, "state": row[name]}
                    for name, value in projected.items()
                    if name in row and value is not None and row[name] != value
                }
                if differences:
                    self.report.add(
                        "conflict",
                        table,
                        identifier,
                        "PROJECTION_DIFFERS_FROM_STATE",
                        differences=differences,
                    )
            combined = {**(projected or {}), **row}
            if table == "workspace_objects" and projected and isinstance(row.get("values"), dict):
                combined["values"] = {**projected.get("values", {}), **row["values"]}
            result[identifier] = combined
        return result

    def index(self, table, rows, *, key="id"):
        result = {}
        for row in rows:
            identifier = row.get(key) if isinstance(row, dict) else None
            if type(identifier) not in (int, str) or not str(identifier):
                self.report.add("failed", table, reason="MISSING_LOCAL_ID", payload=row)
                continue
            identifier = str(identifier)
            if identifier in result:
                self.report.add("conflict", table, identifier, "DUPLICATE_LOCAL_ID", payload=row)
                continue
            result[identifier] = row
        return result

    def read(self):
        self.tables = {
            row[0]
            for row in self.db.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        self.report.sqlite.update(
            userVersion=self.db.execute("PRAGMA user_version").fetchone()[0],
            tables={
                table: {
                    "columns": [
                        row["name"]
                        for row in self.db.execute("SELECT * FROM pragma_table_info(?)", (table,))
                    ],
                    "foreignKeys": [
                        dict(row)
                        for row in self.db.execute(
                            "SELECT * FROM pragma_foreign_key_list(?)", (table,)
                        )
                    ],
                    "rows": self.db.execute(
                        'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
                    ).fetchone()[0],
                }
                for table in sorted(self.tables)
            },
        )
        for failure in self.db.execute("PRAGMA foreign_key_check"):
            self.report.add(
                "failed",
                failure["table"],
                failure["rowid"],
                "SQLITE_FOREIGN_KEY_VIOLATION",
                parentTable=failure["parent"],
                foreignKeyIndex=failure["fkid"],
            )
        state_rows = self.rows("workspace_state")
        if state_rows:
            self.state = json_object(state_rows[0]["state_json"])
            self.report.sqlite["workspaceRevision"] = state_rows[0]["revision"]
        if "workspace_objects" not in self.tables and "objects" not in self.state:
            raise ValueError("The database does not contain a Firefox workspace")
        identities = self.rows("backend_workspace_identity")
        if identities:
            self.workspace_uuid = UUID(identities[0]["workspace_uuid"])
        self.read_objects()
        self.read_nested()
        self.read_provenance()
        self.read_selectors()
        self.report_unknown()

    def read_objects(self):
        normalized = []
        for row in self.rows("workspace_objects"):
            try:
                values = json_object(row["values_json"])
                meta = {
                    key: json.loads(row[column], parse_constant=reject_constant)
                    if column.endswith("_json")
                    else row[column]
                    for column, key in OBJECT_COLUMNS.items()
                    if row.get(column) is not None
                }
            except (ValueError, TypeError) as error:
                self.report.add(
                    "failed",
                    "workspace_objects",
                    row["object_id"],
                    str(error),
                    payload=row,
                )
                continue
            if row.get("last_checked_at") is not None:
                values.setdefault("last_checked_at", row["last_checked_at"])
            normalized.append(
                {
                    "id": row["object_id"],
                    "type": row["object_type"],
                    "values": values,
                    **meta,
                }
            )
        objects = self.merged("workspace_objects", "objects", normalized)
        serialized_ids = set(objects)
        projections = {
            kind: self.index(table, self.rows(table), key="object_id")
            for kind, table in ROOT_TABLES.items()
        }
        by_number = {
            kind: {row["id"]: identifier for identifier, row in rows.items()}
            for kind, rows in projections.items()
        }
        self.projections = projections
        self.by_number = by_number
        for kind, rows in projections.items():
            for identifier in rows:
                objects.setdefault(identifier, {"id": identifier, "type": kind, "values": {}})
        for identifier, payload in objects.items():
            root_type, values = payload.get("type"), payload.get("values", {})
            if not isinstance(root_type, str) or local_type(root_type) not in ROOT_TABLES:
                self.report.add(
                    "unsupported",
                    "workspace_objects",
                    identifier,
                    "UNSUPPORTED_OBJECT_TYPE",
                    payload=payload,
                )
                continue
            if not isinstance(values, dict):
                self.report.add(
                    "failed",
                    "workspace_objects",
                    identifier,
                    "INVALID_OBJECT_VALUES",
                    payload=payload,
                )
                continue
            kind = local_type(root_type)
            payload = {**payload}
            values = dict(values)
            # The per-object JSON carries original fields. Typed columns are projections
            # that can fill gaps in older databases, rather than a second set of objects.
            row = projections[kind].get(identifier, {})
            fields = {item["key"] for item in DEFINITIONS[kind]["fields"]}
            aliases = ALIASES.get(root_type, {}).get("fields", {})
            if kind == "operator":
                aliases = {"adres": "address", "telefon": "phone"}
            for name, value in row.items():
                key = RECRUITMENT_COLUMNS.get(name, name) if kind == "recruitment" else name
                if value is None or key not in fields or key in {"project_id", "operator_id"}:
                    continue
                if key not in aliases.values() or all(
                    old not in values for old, new in aliases.items() if new == key
                ):
                    # Current writers synthesize empty names and Planned status in projections.
                    if (key == "name" and not value) or (
                        key == "status"
                        and kind == "project"
                        and value == "PLANOWANY"
                        and identifier in serialized_ids
                    ):
                        continue
                    values.setdefault(key, value)
            for column, target_kind in (("project_id", "project"), ("operator_id", "operator")):
                if row.get(column) is None:
                    continue
                target = by_number[target_kind].get(row[column])
                if target is None:
                    self.report.add(
                        "failed",
                        ROOT_TABLES[kind],
                        identifier,
                        "UNRESOLVED_SQLITE_REFERENCE",
                        field=column,
                        value=row[column],
                    )
                elif column in values and values[column] not in (None, "", target):
                    self.report.add(
                        "conflict",
                        ROOT_TABLES[kind],
                        identifier,
                        "PROJECTED_REFERENCE_DIFFERS",
                        field=column,
                        value=values[column],
                        projected=target,
                    )
                else:
                    values[column] = target
            for column in ("created_at", "updated_at"):
                if row.get(column) is not None:
                    payload.setdefault(OBJECT_COLUMNS[column], row[column])
            self.objects[(identifier, None, None)] = LocalObject(
                "workspace_objects",
                identifier,
                root_type,
                payload,
                values,
            )

    def read_nested(self):
        assignments = [
            {
                **row,
                "objectId": self.by_number[owner].get(row[f"{owner}_id"]),
                "operatorId": self.by_number["operator"].get(row["operator_id"]),
                "operatorType": row["operator_type"],
            }
            for owner, table in (
                ("project", "projects_operators"),
                ("recruitment", "recruitment_operators"),
            )
            for row in self.rows(table)
        ]
        stored_assignments = self.collection("operatorAssignments")
        pairs = {}
        for row in stored_assignments:
            if not isinstance(row, dict):
                self.report.add(
                    "failed",
                    "workspace_state.operatorAssignments",
                    reason="INVALID_NESTED_PAYLOAD",
                    payload=row,
                )
                continue
            pair = (str(row.get("objectId")), str(row.get("operatorId")))
            if pair in pairs:
                self.report.add(
                    "conflict",
                    "workspace_state.operatorAssignments",
                    row.get("id"),
                    "DUPLICATE_OWNER_OPERATOR_PAIR",
                    payload=row,
                )
                continue
            pairs[pair] = row
        for row in assignments:
            if row["objectId"] is None or row["operatorId"] is None:
                self.report.add(
                    "failed",
                    "operator_assignments",
                    row["id"],
                    "UNRESOLVED_SQLITE_REFERENCE",
                    payload=row,
                )
                continue
            match = pairs.get((row["objectId"], row["operatorId"]))
            if match is not None:
                self.report.mirrored["operator_assignments"] += 1
                if match.get("operatorType") != row["operatorType"]:
                    self.report.add(
                        "conflict",
                        "operator_assignments",
                        match.get("id"),
                        "PROJECTED_OPERATOR_ROLE_DIFFERS",
                        payload=row,
                    )
                continue
            # Join table IDs are regenerated by the extension. The referenced local
            # operator ID is the stable natural key for a normalized-only association.
            self.nested(
                "operator_assignments",
                "operator_assignment",
                {
                    "id": row["operatorId"],
                    "objectId": row["objectId"],
                    "operatorId": row["operatorId"],
                    "operatorType": row["operatorType"],
                    "normalizedOnly": True,
                },
            )
        for row in pairs.values():
            self.nested("workspace_state.operatorAssignments", "operator_assignment", row)

        groups = {row["id"]: row["object_id"] for row in self.rows("geography_groups")}
        for kind in ("project", "recruitment"):
            for owner, record in self.projections[kind].items():
                group = record.get("geography_group_id")
                if group is not None and groups.get(group) != owner:
                    self.report.add(
                        "failed",
                        ROOT_TABLES[kind],
                        owner,
                        "GEOGRAPHY_GROUP_OWNER_MISMATCH",
                        geographyGroupId=group,
                        actualOwner=groups.get(group),
                    )
        dictionaries = {
            kind: {row["id"]: row["value"] for row in self.rows(table)}
            for kind, table in GEOGRAPHY_DICTIONARIES.items()
            if table in self.tables
        }
        geography = []
        used_geography_values = defaultdict(set)
        for row in self.rows("geographies"):
            group = row.get("geography_group_id")
            if group is not None and groups.get(group) != row["object_id"]:
                self.report.add(
                    "failed",
                    "geographies",
                    row["legacy_id"],
                    "GEOGRAPHY_GROUP_OWNER_MISMATCH",
                    payload=row,
                )
                continue
            dictionary = dictionaries.get(row["type"])
            if (
                dictionary is not None
                and dictionary.get(row.get("geography_object_id")) != row["value"]
            ):
                self.report.add(
                    "failed",
                    "geographies",
                    row["legacy_id"],
                    "GEOGRAPHY_DICTIONARY_MISMATCH",
                    payload=row,
                )
            item = {
                "id": row["legacy_id"],
                "objectId": row["object_id"],
                "type": row["type"],
                "role": row["role"],
                "value": row["value"],
                "geographyGroupId": group,
            }
            if row.get("operator_object_id") is not None:
                item["operatorId"] = row["operator_object_id"]
            geography.append(item)
            used_geography_values[row["type"]].add(row.get("geography_object_id"))
        for kind, dictionary in dictionaries.items():
            for identifier in dictionary.keys() - used_geography_values[kind]:
                self.report.add(
                    "skipped",
                    GEOGRAPHY_DICTIONARIES[kind],
                    identifier,
                    "UNREFERENCED_GEOGRAPHY_DICTIONARY_VALUE",
                    value=dictionary[identifier],
                )
        geography_owners = {row["objectId"] for row in geography}
        for group, owner in groups.items():
            root = self.objects.get((owner, None, None))
            if root is None:
                self.report.add(
                    "failed", "geography_groups", group, "GROUP_OWNER_UNRESOLVED", owner=owner
                )
            else:
                root.payload["geographyGroupId"] = group
                if owner not in geography_owners:
                    self.report.add("preserved", "geography_groups", group, owner=owner)

        contacts = [
            {
                "id": row["contact_id"],
                "objectId": row["object_id"],
                "kind": row["kind"],
                "variant_no": row["variant_no"],
                "value": row["value"],
            }
            for row in self.rows("operator_contacts")
        ]
        files = [
            {
                "id": row["source_id"],
                "objectId": row["object_id"],
                "fileType": row["file_type"],
                "url": row["url"],
                "name": row["name"],
                "sourcePageUrl": row["source_page_url"],
                "addedAt": row["added_at"],
            }
            for row in self.rows("file_sources")
        ]
        for kind, table, rows in (
            ("geography", "geographies", geography),
            ("operator_contact", "operator_contacts", contacts),
            ("service_category", "workspace_state.serviceCategories", []),
            ("funding", "financing_rules", self.payload_rows("financing_rules")),
            ("file_source", "file_sources", files),
            ("document", "document_requirements", self.payload_rows("document_requirements")),
        ):
            for row in self.merged(table, NESTED[kind], rows).values():
                self.nested(table, kind, row)

    def payload_rows(self, table):
        for row in self.rows(table):
            try:
                payload = json_object(row["payload_json"])
                if str(payload.get("objectId", row["object_id"])) != row["object_id"]:
                    raise ValueError("Payload and SQLite owner differ")
                yield {"objectId": row["object_id"], **payload}
            except (TypeError, ValueError) as error:
                self.report.add("failed", table, row["row_key"], str(error), payload=row)

    def nested(self, table, kind, payload):
        if not isinstance(payload, dict):
            self.report.add("failed", table, reason="INVALID_NESTED_PAYLOAD", payload=payload)
            return
        owner, identifier = str(payload.get("objectId") or ""), str(payload.get("id") or "")
        root = self.objects.get((owner, None, None))
        if not identifier or not root or root.entity_type not in DEFINITIONS[kind]["parents"]:
            self.report.add(
                "failed",
                table,
                identifier or None,
                "NESTED_ID_OR_OWNER_UNRESOLVED",
                payload=payload,
            )
            return
        item = LocalObject(table, owner, root.root_type, payload, dict(payload), kind, identifier)
        if item.key in self.objects:
            self.report.add("conflict", table, identifier, "DUPLICATE_LOCAL_ID", payload=payload)
            return
        self.objects[item.key] = item

    def read_provenance(self):
        imports = []
        for row in self.rows("import_sources"):
            try:
                snapshot = json_object(row["snapshot_json"])
            except (TypeError, ValueError) as error:
                self.report.add(
                    "failed", "import_sources", row["source_id"], str(error), payload=row
                )
                continue
            imports.append(
                {
                    "id": row["source_id"],
                    "importKey": row["import_key"],
                    "type": row["source_type"],
                    "url": row["url"],
                    "snapshot": snapshot,
                    "importedAt": row["imported_at"],
                }
            )
        self.imports = self.merged("import_sources", "importSources", imports)
        if "local_file_blobs" in self.tables:
            self.blobs = {
                row["file_id"]: dict(row)
                for row in self.db.execute(
                    "SELECT file_id, name, mime_type, size_bytes, uploaded_at FROM local_file_blobs"
                )
            }
        evidence = []
        for row in self.rows("field_evidence"):
            item = {
                "id": row["evidence_id"],
                "objectId": row["object_id"],
                "field": row["field"],
                "pageUrl": row["page_url"],
                "rawValue": row["raw_value"],
                "createdAt": row["created_at"],
            }
            if row.get("target_kind") is not None:
                item["target"] = {"kind": row["target_kind"], "id": row.get("target_id")}
            try:
                for column, key in (
                    ("selector_json", "selector"),
                    ("selector_fallbacks_json", "selectorFallbacks"),
                    ("extraction_json", "extraction"),
                    ("value_at_capture_json", "valueAtCapture"),
                ):
                    if row.get(column) is not None:
                        item[key] = json.loads(row[column], parse_constant=reject_constant)
            except (TypeError, ValueError) as error:
                self.report.add(
                    "failed", "field_evidence", row["evidence_id"], str(error), payload=row
                )
                continue
            evidence.append(item)
        self.evidence = self.merged("field_evidence", "fieldEvidence", evidence)
        self.target_evidence = self.index(
            "workspace_state.importTargetEvidence", self.collection("importTargetEvidence")
        )

    def read_selectors(self):
        groups = {}
        for table, key in (
            ("selector_versions", "selector_uuid"),
            ("selector_recipes", "version_uuid"),
            ("selector_parts", "recipe_uuid"),
            ("selector_locators", "part_uuid"),
        ):
            groups[table] = defaultdict(list)
            for row in self.rows(table):
                groups[table][row[key]].append(row)
        for row in self.rows("selectors"):
            identifier = row["uuid"]
            try:
                self.trees[identifier] = portable_tree(row, groups)
                if row.get("legacy_rule_id"):
                    self.tree_rule_ids[identifier] = row["legacy_rule_id"]
            except (ValueError, TypeError, KeyError) as error:
                self.report.add("failed", "selectors", identifier, str(error), payload=row)
        normalized_rules = [
            {
                "id": row["rule_id"],
                "objectId": row["object_id"],
                "field": row["field"],
                "pageUrl": row["page_url"],
                "sqlite": row,
            }
            for row in self.rows("extraction_rules")
        ]
        self.rules = self.merged("extraction_rules", "rules", normalized_rules)
        evaluations = [
            {
                "uuid": row["uuid"],
                "versionUuid": row["version_uuid"],
                "evaluatedAt": row["evaluated_at"],
                "pageUrl": row["page_url"],
                "result": json_object(row["result_json"]),
            }
            for row in self.rows("selector_evaluations")
        ]
        self.evaluations = self.index("selector_evaluations", evaluations, key="uuid")
        for rule in self.rules.values():
            payload = rule.get("selectorTree")
            if isinstance(payload, dict) and isinstance(payload.get("selector"), dict):
                identifier = payload["selector"].get("uuid")
                if isinstance(identifier, str):
                    if identifier in self.trees:
                        self.report.mirrored["selectors"] += 1
                    else:
                        self.trees[identifier] = payload
            for evaluation in rule.get("selectorEvaluations") or []:
                if not isinstance(evaluation, dict) or not isinstance(evaluation.get("uuid"), str):
                    self.report.add(
                        "failed",
                        "selector_evaluations",
                        reason="MISSING_LOCAL_ID",
                        payload=evaluation,
                    )
                elif evaluation["uuid"] in self.evaluations:
                    self.report.mirrored["selector_evaluations"] += 1
                else:
                    self.evaluations[evaluation["uuid"]] = evaluation

    def report_unknown(self):
        known_state = {
            "version",
            "revision",
            "objects",
            "rules",
            "fieldEvidence",
            "importSources",
            "importTargetEvidence",
            *NESTED.values(),
        }
        for key in sorted(self.state.keys() - known_state):
            self.report.add(
                "unsupported",
                f"workspace_state.{key}",
                reason="UNMAPPED_COLLECTION",
                payload=self.state[key],
            )
        known_tables = {
            "app_meta",
            "workspace_state",
            "workspace_objects",
            *ROOT_TABLES.values(),
            "projects_operators",
            "recruitment_operators",
            "operator_contacts",
            "geographies",
            "geography_groups",
            *GEOGRAPHY_DICTIONARIES.values(),
            "financing_rules",
            "document_requirements",
            "file_sources",
            "import_sources",
            "local_file_blobs",
            "extraction_rules",
            "selectors",
            "selector_versions",
            "selector_recipes",
            "selector_parts",
            "selector_locators",
            "selector_evaluations",
            "field_evidence",
        }
        for table, info in self.report.sqlite["tables"].items():
            if info["rows"] and table not in known_tables:
                status = "skipped" if table.startswith("backend_") else "unsupported"
                self.report.add(
                    status,
                    table,
                    reason="LOCAL_SYNC_BOOKKEEPING" if status == "skipped" else "UNMAPPED_TABLE",
                    rowCount=info["rows"],
                )


def portable_tree(row, groups):
    def children(table, parent, position):
        return sorted(groups[table].get(parent, []), key=lambda item: item[position])

    target = json_object(row["target_json"])
    if target.get("objectId") != row["object_id"] or target.get("field") != row["field"]:
        raise ValueError("Selector columns do not match target JSON")
    selector = {
        "uuid": row["uuid"],
        "target": target,
        "activeVersionUuid": row["active_version_uuid"],
        "createdAt": row["created_at"],
    }
    for column, key in (("source_uuid", "sourceUuid"), ("page_url", "pageUrl")):
        if row.get(column) is not None:
            selector[key] = row[column]
    if row.get("migration_json") is not None:
        selector["migration"] = json_object(row["migration_json"])
    versions = []
    for version in children("selector_versions", row["uuid"], "version_no"):
        recipes = []
        for recipe in children("selector_recipes", version["uuid"], "position"):
            parts = []
            for part in children("selector_parts", recipe["uuid"], "position"):
                locators = [
                    {
                        **json_object(locator["payload_json"]),
                        "uuid": locator["uuid"],
                        "kind": locator["kind"],
                        "order": locator["position"],
                    }
                    for locator in children("selector_locators", part["uuid"], "position")
                ]
                data = {
                    "uuid": part["uuid"],
                    "order": part["position"],
                    "extraction": json_object(part["extraction_json"]),
                    "locators": locators,
                }
                if part.get("join_with") is not None:
                    data["joinWith"] = part["join_with"]
                parts.append(data)
            recipes.append({"uuid": recipe["uuid"], "order": recipe["position"], "parts": parts})
        data = {
            "uuid": version["uuid"],
            "selectorUuid": row["uuid"],
            "versionNo": version["version_no"],
            "status": version["status"],
            "createdFromSnapshotUuid": version["created_from_snapshot_uuid"],
            "artifactType": version["artifact_type"],
            "createdAt": version["created_at"],
            "recipes": recipes,
        }
        for column, key in (("reviewed_at", "reviewedAt"), ("reviewed_by", "reviewedBy")):
            if version.get(column) is not None:
                data[key] = version[column]
        versions.append(data)
    return {"selector": selector, "versions": versions}
