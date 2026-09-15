"""Round-trip browser recipes through SQL and execute them on a later saved HTML snapshot."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest
from extraction_support import capture, count, run_capture
from extraction_support import sessions as extraction_sessions
from fastapi import FastAPI
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import null, select, update

from extraction.api.routes import capture_router
from extraction.exceptions import ExtractionConflict, ExtractionValidationError
from extraction.schemas import capture as dto
from extraction.schemas.evidence import FieldSelector, SourceScope
from extraction.schemas.models import ConcreteValue, FieldObservation
from extraction.schemas.recipes import ExtractionSpec, FieldExtractionRuleRequest
from extraction.services.extraction import ExtractionService
from extraction.services.recipes import RecipeReadError, read_html_literal, stored_rule
from sources.schemas.api import SourceSnapshotCreate
from sources.schemas.models import SourceSnapshot, StoredFile
from sources.services.sources import SourcesService
from sources.services.tracking import as_utc

sessions = extraction_sessions
pytestmark = pytest.mark.asyncio
QUOTE = {
    "exact": "Generator Kompetencji 3.0",
    "prefix": "Program: ",
    "suffix": " oraz informacje dodatkowe.",
}
TEXT = "Program: Generator Kompetencji 3.0 oraz informacje dodatkowe."


def recipe(spec, selector="a.schedule"):
    return {
        "selector": {"type": "CSS", "value": selector} if selector else None,
        "extraction": spec,
    }


def html_capture(spec, raw, *, selector="a.schedule", key="manual", text_content=None, attrs=None):
    data = capture(key=key, value=raw, object_id=None)
    data["scopes"] = data["scopes"][:1]
    data["scope_instances"] = data["scope_instances"][:1]
    data["elements"] = [
        data["elements"][0],
        {
            "client_key": "node",
            "parent_client_key": "doc",
            "element_from": "HTML",
            "text_content": text_content,
            "html": {
                "tag_name": selector.split(".")[0] if selector else "html",
                "attributes_json": attrs,
            },
        },
    ]
    data["values"][0].update(
        scope_instance_client_key="root",
        element_client_key="node",
        char_start=None,
        char_end=None,
        rule=recipe(spec, selector),
    )
    if selector is None:
        data["elements"] = data["elements"][:1]
        data["values"][0]["element_client_key"] = "doc"
    return data


@pytest.mark.parametrize(
    "spec,locator,raw",
    [
        ({"type": "text"}, "h1.title", "Title"),
        ({"type": "attribute", "attribute": "href"}, "a.schedule", "/files/harmonogram-2026.xlsx"),
        ({"type": "attribute", "attribute": "src"}, "img.logo", "/logo.png"),
        ({"type": "selection", "quote": QUOTE}, "p.description", QUOTE["exact"]),
        ({"type": "pageUrl"}, None, "https://example.org/downloads"),
    ],
)
async def test_persist_complete_recipe_and_separate_runtime_evidence(sessions, spec, locator, raw):
    async with sessions() as session:
        _, response = await run_capture(session, html_capture(spec, raw, selector=locator))
        row = await session.scalar(select(FieldSelector))
        assert row.extraction_json == spec
        assert row.selector_string == locator
        assert row.selector_type == ("CSS" if locator else None)
        assert stored_rule(row).extraction.model_dump() == spec
        assert await count(session, SourceScope) == await count(session, FieldObservation) == 1
        observation = await session.get(FieldObservation, response.unresolved_observations[0])
        literal = await session.get(ConcreteValue, observation.concrete_value_id)
        assert literal.raw_value == raw and literal.token_class_id == "text"
        assert literal.element_id is not None
        assert "rule" not in literal.model_dump() and "rule" not in observation.model_dump()


async def test_recipe_versioning_includes_operation_locator_quote_and_annotations(sessions):
    cases = [
        (recipe({"type": "text"}), 1),
        (recipe({"type": "text"}), 1),
        (recipe({"type": "attribute", "attribute": "href"}), 2),
        (recipe({"type": "attribute", "attribute": "src"}), 3),
        (recipe({"type": "attribute", "attribute": "src"}, "a.new"), 4),
        (recipe({"type": "selection", "quote": QUOTE}, "a.new"), 5),
        (recipe({"type": "selection", "quote": {**QUOTE, "exact": "Generator 4"}}, "a.new"), 6),
        (recipe({"type": "selection", "quote": {**QUOTE, "prefix": ""}}, "a.new"), 7),
        (recipe({"type": "selection", "quote": {**QUOTE, "suffix": ""}}, "a.new"), 8),
    ]
    last = {**cases[-1][0], "confidence": 0.8}
    cases.extend([(last, 9), ({**last, "discovered_by": "PATTERN"}, 10)])
    async with sessions() as session:
        for index, (rule, version) in enumerate(cases):
            data = html_capture({"type": "text"}, "literal", key=f"v{index}")
            data["values"][0]["rule"] = rule
            await run_capture(session, data)
            rows = list(
                await session.scalars(select(FieldSelector).order_by(FieldSelector.version))
            )
            assert len(rows) == version
            assert rows[-1].version == version and rows[-1].valid_to is None
            for old, new in zip(rows[:-1], rows[1:], strict=True):
                assert as_utc(old.valid_to) == as_utc(new.valid_from)
        assert rows[0].extraction_json == {"type": "text"}
        assert rows[1].extraction_json == {"type": "attribute", "attribute": "href"}
        assert rows[4].extraction_json["quote"] == QUOTE


async def test_scope_rollover_carries_the_complete_recipe(sessions):
    async with sessions() as session:
        data = html_capture(
            {"type": "selection", "quote": QUOTE}, QUOTE["exact"], selector="p.description"
        )
        await run_capture(session, data)
        data["capture_key"] = "new-root"
        data["scopes"][0]["selector"]["value"] = "body"
        data["values"][0]["rule"] = None
        await run_capture(session, data)
        rows = list(await session.scalars(select(FieldSelector).order_by(FieldSelector.id)))
        assert len(rows) == 2 and rows[0].scope_id != rows[1].scope_id
        assert (
            rows[1].extraction_json
            == rows[0].extraction_json
            == {"type": "selection", "quote": QUOTE}
        )


async def test_repeated_records_cannot_teach_different_extraction_with_same_locator(sessions):
    data = capture(rows=2)
    for value in data["values"]:
        value["char_start"] = value["char_end"] = None
    data["values"][1]["rule"]["extraction"] = {"type": "attribute", "attribute": "href"}
    async with sessions() as session:
        with pytest.raises(ExtractionValidationError, match="share one reusable field recipe"):
            await run_capture(session, data)
        assert await count(session, FieldSelector) == await count(session, ConcreteValue) == 0


@pytest.mark.parametrize(
    "rule",
    [
        recipe({"type": "attribute"}),
        recipe({"type": "attribute", "attribute": "onclick"}),
        recipe({"type": "attribute", "attribute": "HREF"}),
        recipe({"type": "selection", "quote": {"exact": "x"}}),
        recipe({"type": "selection", "quote": {"exact": "", "prefix": "", "suffix": ""}}),
        recipe({"type": "text", "attribute": "href"}),
        recipe({"type": "unknown"}),
        recipe({"type": "text"}, None),
        recipe({"type": "attribute", "attribute": "href"}, None),
        recipe({"type": "selection", "quote": QUOTE}, None),
        recipe({"type": "pageUrl"}),
    ],
)
async def test_invalid_rules_are_rejected_by_discriminated_contract(rule):
    with pytest.raises(ValidationError):
        FieldExtractionRuleRequest.model_validate(rule)


async def test_selector_only_payload_is_not_silently_assumed_to_mean_text():
    data = capture()
    data["values"][0]["selector"] = data["values"][0].pop("rule")["selector"]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        dto.CaptureRequest.model_validate(data)


@pytest.mark.parametrize(
    "invalid_json",
    [
        {"type": "attribute"},
        {"type": "attribute", "attribute": "onclick"},
        {"type": "selection", "quote": {"exact": "x"}},
        {"type": "pageUrl"},
        {"type": "text", "extra": 1},
        ["text"],
    ],
)
async def test_invalid_db_recipe_is_rejected_before_adapter_io(sessions, invalid_json):
    class NeverCalled:
        async def extract(self, *args, **kwargs):
            pytest.fail("Malformed stored JSON must not reach the adapter")

    async with sessions() as session:
        await run_capture(session, capture())
        await session.execute(update(FieldSelector).values(extraction_json=invalid_json))
        await session.commit()
        service = ExtractionService(session, NeverCalled())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
        )
        with pytest.raises(ExtractionValidationError, match="Invalid stored field recipe"):
            await service.execute(run.id, "invalid-db")
        assert (await service.get_run(run.id)).status == "pending"
        assert await count(session, ConcreteValue) == 1


@pytest.mark.parametrize("scope_rollover", [False, True])
async def test_legacy_unknown_recipe_requires_explicit_rediscovery(sessions, scope_rollover):
    class NeverCalled:
        async def extract(self, *args, **kwargs):
            pytest.fail("Unknown legacy behavior must not be guessed")

    async with sessions() as session:
        await run_capture(session, capture())
        await session.execute(update(FieldSelector).values(extraction_json=null()))
        await session.commit()
        service = ExtractionService(session, NeverCalled())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
        )
        with pytest.raises(ExtractionConflict, match="rediscovery"):
            await service.execute(run.id, "legacy")
        data = capture(key="rediscover")
        if scope_rollover:
            data["scopes"][0]["selector"]["value"] = "body"
        await run_capture(session, data)
        rows = list(await session.scalars(select(FieldSelector).order_by(FieldSelector.id)))
        assert len(rows) == 2 and rows[0].extraction_json is None
        assert rows[1].extraction_json == {"type": "text"}
        if scope_rollover:
            assert rows[1].scope_id != rows[0].scope_id and rows[1].version == 1
            assert (await session.get(SourceScope, rows[0].scope_id)).valid_to is not None
        else:
            assert rows[0].valid_to is not None and rows[1].version == 2


class SavedHTMLAdapter:
    """Test fixture locator/parser; production HOW is read_html_literal.

    Only the tag.class locators used by these HTML fixtures are supported here.
    It receives no plugin payload or taught literal, and reads acquisition storage.
    """

    def __init__(self, sessions):
        self.sessions = sessions
        self.received_rules = []

    async def extract(self, snapshot, definitions, *, capture_key):
        async with self.sessions() as session:
            stored_file = await session.get(StoredFile, snapshot.file_id)
            html = Path(stored_file.storage_key).read_text()
        root = ElementTree.fromstring(html)
        (definition,) = definitions.selectors
        self.received_rules.append(definition.rule.model_dump(mode="json"))
        rule = definition.rule
        if rule.selector:
            tag, css_class = rule.selector.value.split(".", 1)
            matches = root.findall(f".//{tag}[@class='{css_class}']")
            assert len(matches) == 1
            node = matches[0]
        else:
            node = root
        content = "".join(node.itertext())
        data = html_capture(
            rule.extraction.model_dump(),
            "placeholder",
            selector=rule.selector.value if rule.selector else None,
            key=capture_key,
            text_content=content,
            attrs=dict(node.attrib),
        )
        (scope,) = definitions.scopes
        data["scopes"][0].update(
            name=scope.name,
            business_entity_id=scope.business_entity_id,
            selector={"type": scope.selector_type, "value": scope.selector_string},
        )
        value = data["values"][0]
        value.update(
            rule=None,
            discovered_by="AUTOMATIC",
            confirmed_by_human=False,
            business_entity_field_id=definition.business_entity_field_id,
            normalized_value=None,
        )
        try:
            value.update(
                asdict(
                    read_html_literal(
                        rule.extraction,
                        text_content=content,
                        attributes=dict(node.attrib),
                        page_url=snapshot.page_url,
                    )
                )
            )
        except RecipeReadError as error:
            data["values"] = []
            data["issues"] = [
                {
                    "code": error.code,
                    "message": str(error),
                    "scope_instance_client_key": "root",
                    "business_entity_field_id": definition.business_entity_field_id,
                }
            ]
        return dto.CaptureRequest.model_validate(data)


@pytest.mark.parametrize("operation", ["href", "selection", "pageUrl"])
async def test_teach_recipe_then_execute_it_on_a_later_stored_snapshot(
    sessions, tmp_path, operation
):
    if operation == "href":
        spec = {"type": "attribute", "attribute": "href"}
        locator = "a.schedule"
        old, expected = "/files/harmonogram-2026.xlsx", "/files/harmonogram-2027.xlsx"
        html = (
            '<html><a class="schedule" href="/files/harmonogram-2027.xlsx">'
            "Pobierz harmonogram</a></html>"
        )
    elif operation == "selection":
        spec = {"type": "selection", "quote": QUOTE}
        locator = "p.description"
        old = expected = QUOTE["exact"]
        html = f'<html><p class="description">Nowa edycja. {TEXT}</p></html>'
    else:
        spec = {"type": "pageUrl"}
        locator = None
        old, expected = "https://example.org/downloads", "https://example.org/2027#harmonogram"
        html = "<html><p>A later saved page</p></html>"
    path = tmp_path / "snapshot-2027.html"
    path.write_text(html)
    async with sessions() as session:
        # Both acquisition metadata and recipe are committed before creating the adapter.
        await run_capture(session, html_capture(spec, old, selector=locator))
        file = StoredFile(storage_key=str(path), mime_type="text/html")
        session.add(file)
        await session.flush()
        snapshot = SourceSnapshot(
            source_id=60,
            file_id=file.id,
            page_url="https://example.org/2027#harmonogram",
            fetched_at=datetime(2027, 1, 1, tzinfo=UTC),
            mime_type="text/html",
        )
        session.add(snapshot)
        await session.commit()
        snapshot_id = snapshot.id
    # Fresh session/adapter: the only recipe source is the database.
    adapter = SavedHTMLAdapter(sessions)
    async with sessions() as session:
        service = ExtractionService(session, adapter)
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=snapshot_id, extractor_version="html-test")
        )
        response = await service.execute(run.id, "automatic-later-snapshot")
        observation = await service.get_observation(response.unresolved_observations[0])
        (literal,) = observation.concrete_values
        assert literal.raw_value == expected
        assert adapter.received_rules[0]["extraction"] == spec
        assert await count(session, FieldSelector) == 1
        if operation == "href":
            assert literal.raw_value != "Pobierz harmonogram" and literal.char_start is None
        elif operation == "selection":
            assert literal.raw_value != TEXT and literal.char_start == len("Nowa edycja. Program: ")
        else:
            assert adapter.received_rules[0]["selector"] is None and literal.char_start is None


@pytest.mark.parametrize("mutation", ["new-rule", "same-rule", "mutate-spec", "mutate-scope"])
async def test_adapter_cannot_rewrite_or_mutate_definitions(sessions, mutation):
    class Adapter:
        async def extract(self, snapshot, definitions, *, capture_key):
            data = capture(key=capture_key, confirmed=False)
            data["values"][0].update(rule=None, discovered_by="AUTOMATIC")
            if mutation == "new-rule":
                data["values"][0]["rule"] = recipe({"type": "attribute", "attribute": "href"})
            elif mutation == "same-rule":
                data["values"][0]["rule"] = definitions.selectors[0].rule.model_dump()
            elif mutation == "mutate-spec":
                definitions.selectors[0].rule.extraction = TypeAdapter(
                    ExtractionSpec
                ).validate_python({"type": "attribute", "attribute": "href"})
            else:
                definitions.scopes[0].selector_string = "main"
                data["scopes"][0]["selector"]["value"] = "main"
            return dto.CaptureRequest.model_validate(data)

    async with sessions() as session:
        await run_capture(session, capture())
        service = ExtractionService(session, Adapter())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="bad-adapter")
        )
        with pytest.raises(ExtractionValidationError, match="Adapter mutated|omit field recipe"):
            await service.execute(run.id, "bad-adapter")
        assert (await service.get_run(run.id)).status == "failed"
        assert await count(session, ConcreteValue) == await count(session, FieldSelector) == 1
        assert (await session.scalar(select(FieldSelector))).extraction_json == {"type": "text"}


@pytest.mark.parametrize("same_row_id", [True, False])
async def test_definition_fingerprint_detects_how_change_during_execution(sessions, same_row_id):
    class Adapter:
        async def extract(self, snapshot, definitions, *, capture_key):
            async with sessions() as concurrent:
                if same_row_id:
                    # Defense against an out-of-band update without a version rollover.
                    await concurrent.execute(
                        update(FieldSelector).values(
                            extraction_json={"type": "attribute", "attribute": "href"},
                        )
                    )
                    await concurrent.commit()
                else:
                    data = capture(key="rediscovery")
                    data["values"][0].update(char_start=None, char_end=None)
                    data["values"][0]["rule"]["extraction"] = {
                        "type": "attribute",
                        "attribute": "href",
                    }
                    await run_capture(concurrent, data)
            data = capture(key=capture_key, confirmed=False)
            data["values"][0].update(rule=None, discovered_by="AUTOMATIC")
            return dto.CaptureRequest.model_validate(data)

    async with sessions() as session:
        await run_capture(session, capture())
        service = ExtractionService(session, Adapter())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
        )
        with pytest.raises(ExtractionConflict, match="definitions changed"):
            await service.execute(run.id, "stale-execution")
        assert (await service.get_run(run.id)).status == "pending"
        assert await count(session, ConcreteValue) == (1 if same_row_id else 2)


async def test_snapshot_registration_preserves_page_url_and_fragment(sessions):
    async with sessions() as session:
        service = SourcesService(session)
        explicit = "https://example.org/view?file=a%2Fb#selected"
        snapshot = await service.create_snapshot(60, SourceSnapshotCreate(page_url=explicit))
        assert (await service.get_snapshot(60, snapshot.id)).page_url == explicit
        fallback = await service.create_snapshot(60, SourceSnapshotCreate())
        assert fallback.page_url == "https://example.org/downloads"


async def test_page_url_evidence_must_match_recorded_url(sessions):
    async with sessions() as session:
        with pytest.raises(ExtractionValidationError, match="URL recorded"):
            await run_capture(
                session, html_capture({"type": "pageUrl"}, "https://wrong.example", selector=None)
            )
        assert await count(session, ConcreteValue) == 0


async def test_unknown_snapshot_url_cannot_execute_page_url_rule(sessions):
    async with sessions() as session:
        await run_capture(
            session,
            html_capture({"type": "pageUrl"}, "https://example.org/downloads", selector=None),
        )
        session.add(
            SourceSnapshot(id=101, source_id=60, fetched_at=datetime(2027, 1, 1, tzinfo=UTC))
        )
        await session.commit()
        service = ExtractionService(session, SavedHTMLAdapter(sessions))
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=101, extractor_version="test")
        )
        with pytest.raises(ExtractionConflict, match="recorded snapshot URL"):
            await service.execute(run.id, "unknown-url")


@pytest.mark.parametrize(
    "content,quote,expected_code",
    [
        ("Same Same", {"exact": "Same", "prefix": "", "suffix": ""}, "AMBIGUOUS_MATCH"),
        ("Other", QUOTE, "VALUE_NOT_FOUND"),
        (TEXT, {**QUOTE, "prefix": "Wrong: "}, "VALUE_NOT_FOUND"),
    ],
)
async def test_selection_reader_never_falls_back_to_paragraph(content, quote, expected_code):
    spec = TypeAdapter(ExtractionSpec).validate_python({"type": "selection", "quote": quote})
    with pytest.raises(RecipeReadError) as error:
        read_html_literal(spec, text_content=content)
    assert error.value.code == expected_code


async def test_quote_context_disambiguates_and_preserves_unicode_offsets():
    spec = TypeAdapter(ExtractionSpec).validate_python(
        {
            "type": "selection",
            "quote": {"exact": "GK", "prefix": "😀 ", "suffix": "!"},
        }
    )
    result = read_html_literal(spec, text_content="GK? 😀 GK!")
    assert result.raw_value == "GK" and (result.char_start, result.char_end) == (6, 8)


async def test_openapi_exposes_discriminated_specs_and_one_canonical_rule():
    app = FastAPI()
    app.include_router(capture_router)
    schemas = app.openapi()["components"]["schemas"]
    extraction = schemas["FieldExtractionRuleRequest"]["properties"]["extraction"]
    assert extraction["discriminator"]["propertyName"] == "type"
    assert set(extraction["discriminator"]["mapping"]) == {
        "text",
        "attribute",
        "selection",
        "pageUrl",
    }
    assert "oneOf" in extraction
    properties = schemas["ValueRequest"]["properties"]
    assert "rule" in properties and "selector" not in properties
