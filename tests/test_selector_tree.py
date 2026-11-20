"""Representative fixtures from extension 7dec21c's unified-selector tests."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from extraction.schemas.selector_tree import (
    SelectorLocator,
    SelectorTree,
    validate_selector_evaluation,
)
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version

PAGE = "http://selector.test/project"
CREATED = "2026-11-17T10:00:00.000Z"


def uuid():
    return str(uuid4())


def css(selector, order=0):
    return {"uuid": uuid(), "kind": "css_path", "order": order, "selector": selector}


def part(*locators, order=0, extraction=None, **options):
    return {
        "uuid": uuid(),
        "order": order,
        "extraction": extraction or {"type": "text"},
        "locators": list(locators),
        **options,
    }


def recipe(*parts, order=0):
    return {"uuid": uuid(), "order": order, "parts": list(parts)}


def tree(*recipes, status="active"):
    selector_uuid, version_uuid = uuid(), uuid()
    return {
        "selector": {
            "uuid": selector_uuid,
            "target": {
                "objectId": "R_42",
                "field": "name",
                "target": {"kind": "case", "id": "R_42"},
            },
            "pageUrl": PAGE,
            "activeVersionUuid": version_uuid if status == "active" else None,
            "createdAt": CREATED,
        },
        "versions": [
            {
                "uuid": version_uuid,
                "selectorUuid": selector_uuid,
                "versionNo": 1,
                "status": status,
                "createdAt": CREATED,
                "createdFromSnapshotUuid": None,
                "artifactType": "rendered_dom",
                "recipes": list(recipes) or [recipe(part(css("#funding")))],
            }
        ],
    }


def evaluate(definition, html):
    version = SelectorTree.model_validate(definition).versions[0]
    result = evaluate_selector_version(version, HtmlSelectorRuntime(html, PAGE))
    validate_selector_evaluation(result, version)
    return result


def reserved_locators():
    dom_path = {"root": "document", "segments": [{"tagName": "html", "siblingIndex": 0}]}
    point = {"path": dom_path, "textNodeIndex": 0, "offset": 1}
    position = {
        "start": 1,
        "end": 3,
        "coordinates": {
            "representation": "rendered_dom_text",
            "representationVersion": "backend-v1",
            "offsetUnit": "unicode_codepoint",
            "contentHash": {"algorithm": "sha256", "value": "a" * 64},
        },
    }
    return [
        ("dom_path", dom_path),
        (
            "dom_range",
            {"start": point, "end": {**point, "offset": 3}, "offsetUnit": "utf16_code_unit"},
        ),
        ("text_position", position),
        ("exact_pos", {**position, "exact": "😀"}),
        ("text_fragment", {"textStart": "IV kwartał", "textEnd": "2026", "prefix": "Termin: "}),
    ]


@pytest.mark.parametrize("kind,payload", reserved_locators())
def test_reserved_payload_round_trip_and_runtime_status(kind, payload):
    locator = {"uuid": uuid(), "kind": kind, "order": 0, "payload": payload}
    definition = tree(recipe(part(locator)))
    assert SelectorTree.model_validate(definition).portable() == definition
    result = evaluate(definition, '<p id="funding">IV kwartał 😀</p>')
    assert result.status == "unsupported"
    assert result.recipe_results[0].part_results[0].locator_results[0].match_count == 0


def test_requires_exact_position_digest_and_range_units():
    for kind, data in reserved_locators():
        data = deepcopy(data)
        locator = {"uuid": uuid(), "kind": kind, "order": 0, "payload": data}
        if kind in {"exact_pos", "text_position"}:
            del data["coordinates"]["contentHash"]
        elif kind == "dom_range":
            data["offsetUnit"] = "unicode_codepoint"
        else:
            continue
        with pytest.raises(ValidationError):
            TypeAdapter(SelectorLocator).validate_python(locator)


@pytest.mark.parametrize(
    "damage",
    ["foreign", "duplicate_uuid", "duplicate_order", "empty", "wrong_active", "two_active"],
)
def test_rejects_invalid_structure(damage):
    definition = tree()
    version = definition["versions"][0]
    locators = version["recipes"][0]["parts"][0]["locators"]
    match damage:
        case "foreign":
            version["selectorUuid"] = uuid()
        case "duplicate_uuid":
            locators.append({**locators[0], "order": 1})
        case "duplicate_order":
            locators.append(css("#other"))
        case "empty":
            locators.clear()
        case "wrong_active":
            definition["selector"]["activeVersionUuid"] = uuid()
        case "two_active":
            other = tree()["versions"][0]
            other.update(versionNo=2, selectorUuid=definition["selector"]["uuid"])
            definition["versions"].append(other)
    with pytest.raises(ValidationError):
        SelectorTree.model_validate(definition)


def test_browser_fixture_for_cross_node_quote_xpath_attribute_and_duplicates():
    html = (
        '<p id="description">Funding <strong>80</strong><span>%</span> today</p>'
        '<meta name="funding" content="80%">'
        '<p id="duplicate">repeat</p><p id="duplicate">repeat</p>'
    )
    quote = {"exact": "80%", "prefix": "Funding ", "suffix": " today"}
    locators = [
        css("#description"),
        {"kind": "xpath", "uuid": uuid(), "order": 1, "expression": "//p[@id='description']"},
        {"kind": "text_quote", "uuid": uuid(), "order": 2, "quote": quote},
    ]
    result = evaluate(
        tree(recipe(part(*locators, extraction={"type": "selection", "quote": quote}))), html
    )
    assert result.raw_value == "80%"
    assert [r.status for r in result.recipe_results[0].part_results[0].locator_results] == [
        "success"
    ] * 3
    attribute = part(css("meta[name=funding]"), extraction={"type": "attribute", "name": "content"})
    assert evaluate(tree(recipe(attribute)), html).raw_value == "80%"
    for kind, metadata in [
        ("element_id", {"elementId": "duplicate"}),
        ("text_quote", {"quote": {"exact": "repeat"}}),
    ]:
        loc = {"kind": kind, "uuid": uuid(), "order": 0, **metadata}
        ambiguous = evaluate(tree(recipe(part(loc))), html)
        assert ambiguous.status == "ambiguous"
        assert ambiguous.recipe_results[0].part_results[0].locator_results[0].match_count == 2
    for expression in ("//*[", "string(//p)"):
        loc = {"kind": "xpath", "uuid": uuid(), "order": 0, "expression": expression}
        assert evaluate(tree(recipe(part(loc))), html).status == "error"


def test_selection_reuses_context_and_preserves_attribute_whitespace_and_href_base():
    part_spec = part(
        css("#funding"),
        extraction={
            "type": "selection",
            "quote": {"exact": "80%", "prefix": "Funding ", "suffix": " today"},
        },
    )
    assert (
        evaluate(tree(recipe(part_spec)), '<p id="funding">Funding 85% today</p>').raw_value
        == "85%"
    )
    html = (
        '<base href="/files/"><a href="offer 2026.pdf">'
        '<span id="link" title="  IV kwartał 😀  ">Download</span></a>'
    )
    for name, value in [
        ("href", "http://selector.test/files/offer%202026.pdf"),
        ("title", "  IV kwartał 😀  "),
    ]:
        definition = tree(
            recipe(part(css("#link"), extraction={"type": "attribute", "name": name}))
        )
        assert evaluate(definition, html).raw_value == value


def test_consensus_preserves_diagnostics_and_uses_order_and_exact_strings():
    year = part(css("#year"), css(".missing", 1), joinWith="ignored")
    quarter = part(css("#quarter"), order=1, joinWith=" - ")
    value = tree(
        recipe(quarter, year, order=1),
        recipe(part(css("#full")), order=0),
    )
    html = '<p id="year">2026</p><p id="quarter">IV kwartał 😀</p>'
    success = evaluate(value, html + '<p id="full">2026 - IV kwartał 😀</p>')
    assert success.raw_value == "2026 - IV kwartał 😀"
    assert success.recipe_results[1].part_results[0].locator_results[1].status == "not_found"
    assert evaluate(value, html).status == "not_found"
    assert evaluate(value, html + '<p id="full">2026 - iv kwartał 😀</p>').status == "conflict"
    year["locators"].append(css("#quarter", 2))
    assert evaluate(value, html + '<p id="full">2026 - IV kwartał 😀</p>').status == "conflict"


def test_bounds_follow_utf16_code_units_and_missing_part_fails_recipe():
    definition = tree(recipe(part(css("#funding"))))
    assert evaluate(definition, '<p id="funding">' + "😀" * 50_001 + "</p>").status == "error"
    definition["versions"][0]["recipes"][0]["parts"].append(part(css("#absent"), order=1))
    assert evaluate(definition, '<p id="funding">80</p>').status == "not_found"


def test_dom_query_ignores_template_contents_and_html_attributes_are_case_insensitive():
    html = '<template><p id="funding">hidden</p></template><p id="funding" title="  ">shown</p>'
    definition = tree(
        recipe(part(css("#funding"), extraction={"type": "attribute", "name": "TITLE"}))
    )
    assert evaluate(definition, html).raw_value == "  "
