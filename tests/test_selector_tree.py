"""Representative fixtures from extension 7dec21c's unified-selector tests."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from extraction.schemas.selector_tree import (
    SelectorEvaluationResult,
    SelectorLocator,
    SelectorTree,
    validate_selector_evaluation,
)
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from monitoring.report import validate_consensus

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


RECRUITMENT_LOCATOR = "div.info-top p.wp-block-paragraph"
OLD_ANNOUNCEMENT = "Nabór rozpocznie się 01 października 2026"
NEW_ANNOUNCEMENT = "Nabór zakończy się 29 listopada 2026"


def announcement(value):
    return (
        '<!doctype html><meta charset="utf-8"><div class="info-top">'
        f'<p class="wp-block-paragraph" id="announcement">{value}</p></div>'
        "<footer>Kontakt i inne informacje</footer>"
    )


def recruitment_tree(extraction):
    return tree(
        recipe(
            part(
                css(RECRUITMENT_LOCATOR),
                css("#announcement", order=1),
                {
                    "uuid": uuid(),
                    "kind": "xpath",
                    "expression": '//div[@class="info-top"]/p',
                    "order": 2,
                },
                {
                    "uuid": uuid(),
                    "kind": "text_quote",
                    "quote": {"exact": OLD_ANNOUNCEMENT},
                    "order": 3,
                },
                extraction=extraction,
            )
        )
    )


def locator_results(result):
    return result.recipe_results[0].part_results[0].locator_results


def test_dynamic_announcement_css_and_xpath_agree_after_the_quote_disappears():
    definition = recruitment_tree({"type": "text"})
    assert evaluate(definition, announcement(OLD_ANNOUNCEMENT)).raw_value == OLD_ANNOUNCEMENT
    result = evaluate(definition, announcement(NEW_ANNOUNCEMENT))
    assert result.status == "success"
    assert result.raw_value == NEW_ANNOUNCEMENT
    css_result, fallback, xpath, quote = locator_results(result)
    for locator in (css_result, fallback, xpath):
        assert (locator.status, locator.match_count, locator.raw_value) == (
            "success",
            1,
            NEW_ANNOUNCEMENT,
        )
    assert quote.status == "not_found"
    assert quote.candidate is None

    disagreement = evaluate(
        definition, announcement(NEW_ANNOUNCEMENT) + f"<p>{OLD_ANNOUNCEMENT}</p>"
    )
    assert disagreement.status == "conflict"
    assert evaluate(definition, "<p>Different target</p>").status == "not_found"


def test_old_exact_selection_retains_failure_and_exact_public_element_text():
    exact = {"type": "selection", "quote": {"exact": OLD_ANNOUNCEMENT}}
    definition = recruitment_tree(exact)
    assert evaluate(definition, announcement(OLD_ANNOUNCEMENT)).raw_value == OLD_ANNOUNCEMENT
    original_spacing = f" \n{NEW_ANNOUNCEMENT}  "
    result = evaluate(
        definition,
        announcement(original_spacing + "<textarea>private</textarea><script>private</script>"),
    )
    assert result.status == "error" and result.raw_value is None
    for locator in locator_results(result)[:3]:
        assert locator.match_count == 1
        assert locator.extraction_error == "selection_quote_mismatch"
        assert locator.candidate.portable() == {
            "rawText": original_spacing,
            "source": "matched_element_text",
            "verified": False,
        }
    assert locator_results(result)[3].candidate is None

    for value in ("password: private", "x" * 4097, "<input value=private>"):
        assert locator_results(evaluate(definition, announcement(value)))[0].candidate is None
    broad = tree(recipe(part(css("body"), extraction=exact)))
    assert locator_results(evaluate(broad, announcement(NEW_ANNOUNCEMENT)))[0].candidate is None
    missing = evaluate(definition, "<div>Something else</div>")
    assert all(locator.candidate is None for locator in locator_results(missing))


def test_boundary_extraction_has_no_previous_literal_and_requires_a_unique_span():
    extraction = {"type": "text_between", "start": "Numer:", "end": "Status:"}
    definition = recruitment_tree(extraction)
    for number in ("123-AB", "456-CD"):
        result = evaluate(definition, announcement(f"Numer: <b>{number}</b> Status: otwarty"))
        assert result.raw_value == number
    result = evaluate(definition, announcement("Numer: 123 Status: Numer: 456 Status:"))
    assert locator_results(result)[0].extraction_error == "text_boundary_ambiguous"
    result = evaluate(definition, announcement("Numer: 123"))
    assert locator_results(result)[0].extraction_error == "text_boundary_missing"
    for start in ("  ", "😀" * 129):
        with pytest.raises(ValidationError, match="Text boundaries"):
            SelectorTree.model_validate(recruitment_tree({**extraction, "start": start}))


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"matchCount": 0}, "one located target"),
        ({"status": "success", "rawValue": "forged"}, "one located target"),
        ({"rawValue": "forged"}, "no raw value"),
        ({"extractionError": "attribute_missing"}, "configured method"),
        ({"extractionError": "not_a_code"}, "extractionError"),
        ({"candidate": {"verified": True}}, "explicitly unverified"),
        ({"candidate": {"verified": 0}}, "explicitly unverified"),
        ({"candidate": {"rawText": "😀" * 2049}}, "bounded, non-sensitive"),
        ({"candidate": {"rawText": "access_token\u00a0=\u00a0secret"}}, "bounded, non-sensitive"),
        ({"candidate": {"rawText": "bad\x00data"}}, "bounded, non-sensitive"),
        ({"candidate": {"source": "page_text"}}, "source"),
        ({"candidate": {"sourceSnapshotId": 84}}, "Extra inputs"),
    ],
)
def test_diagnostic_candidate_validation(changes, expected):
    definition = recruitment_tree({"type": "selection", "quote": {"exact": OLD_ANNOUNCEMENT}})
    version = SelectorTree.model_validate(definition).versions[0]
    report = evaluate(definition, announcement(NEW_ANNOUNCEMENT)).portable()
    locator = report["recipeResults"][0]["partResults"][0]["locatorResults"][0]
    if "candidate" in changes:
        locator["candidate"].update(changes["candidate"])
    else:
        locator.update(changes)
    with pytest.raises(ValueError, match=expected):
        result = SelectorEvaluationResult.model_validate(report)
        validate_selector_evaluation(result, version)
        validate_consensus(result, version)


def test_diagnostic_candidate_cannot_be_attached_to_a_text_quote_locator_or_promoted():
    definition = recruitment_tree({"type": "selection", "quote": {"exact": OLD_ANNOUNCEMENT}})
    version = SelectorTree.model_validate(definition).versions[0]
    failed = evaluate(definition, announcement(NEW_ANNOUNCEMENT))
    quote = locator_results(failed)[3]
    report = failed.portable()
    locators = report["recipeResults"][0]["partResults"][0]["locatorResults"]
    locators[3] = {**locators[0], "locatorUuid": str(quote.locator_uuid)}
    result = SelectorEvaluationResult.model_validate(report)
    with pytest.raises(ValueError, match="requires an element locator"):
        validate_selector_evaluation(result, version)

    report = failed.portable()
    report.update(status="success", rawValue=NEW_ANNOUNCEMENT)
    result = SelectorEvaluationResult.model_validate(report)
    with pytest.raises(ValueError, match="outcome does not follow"):
        validate_consensus(result, version)


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
