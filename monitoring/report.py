"""Validate reported consensus using the existing SelectorTree aggregation rules."""

from extraction.schemas.selector_tree import ordered
from extraction.services.selector_resolver import (
    summarize_part,
    summarize_recipe,
    summarize_version,
)


def same_outcome(reported, expected):
    if (
        (reported.raw_value is not None and "\x00" in reported.raw_value)
        or reported.status != expected.status
        or (reported.status == "success" and reported.raw_value != expected.raw_value)
    ):
        raise ValueError("Reported outcome does not follow from its diagnostics")


def validate_consensus(result, definition):
    recipes = {item.recipe_uuid: item for item in result.recipe_results}
    for recipe in ordered(definition.recipes):
        reported_recipe = recipes[recipe.uuid]
        parts = {item.part_uuid: item for item in reported_recipe.part_results}
        for part in ordered(recipe.parts):
            reported_part = parts[part.uuid]
            for locator in reported_part.locator_results:
                if (
                    locator.raw_value is not None
                    and "\x00" in locator.raw_value
                    or locator.status == "conflict"
                    or locator.status in {"not_found", "unsupported"}
                    and locator.match_count != 0
                    or locator.status == "ambiguous"
                    and locator.match_count < 2
                ):
                    raise ValueError("Invalid locator status and match count")
            same_outcome(reported_part, summarize_part(part, reported_part.locator_results))
        same_outcome(
            reported_recipe,
            summarize_recipe(recipe, [parts[part.uuid] for part in ordered(recipe.parts)]),
        )
    same_outcome(
        result,
        summarize_version(
            definition, [recipes[recipe.uuid] for recipe in ordered(definition.recipes)]
        ),
    )
