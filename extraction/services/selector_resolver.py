"""Evaluate the extension's selector graph against stored HTML."""

import re
from array import array
from dataclasses import dataclass
from functools import cached_property
from itertools import islice
from string import ascii_lowercase, ascii_uppercase

import html5lib
from cssselect2 import ElementWrapper
from lxml import etree
from whatwg_url import urljoin

from extraction.schemas.selector_tree import (
    JS_SPACE,
    MAX_CANDIDATE_LENGTH,
    MAX_RAW_LENGTH,
    ExtractionError,
    LocatorEvaluationResult,
    PartEvaluationResult,
    RecipeEvaluationResult,
    SelectorEvaluationResult,
    ordered,
    safe_candidate_text,
    utf16_length,
)

FAILURE_ORDER = ("conflict", "ambiguous", "error", "unsupported", "not_found")
SPACES = re.compile("[" + re.escape(JS_SPACE) + "]+")
SKIP_TEXT = {"script", "style", "noscript", "template"}
PRIVATE_TEXT_TAGS = SKIP_TEXT | {
    "iframe",
    "frame",
    "object",
    "embed",
    "input",
    "textarea",
    "select",
    "base",
}
HTML_ATTRIBUTE_CASE = str.maketrans(ascii_uppercase, ascii_lowercase)


def clean(value):
    return SPACES.sub(" ", value).strip(" ")


def hits(text, value):
    start = 0
    while (found := text.find(value, start)) != -1:
        yield found
        start = found + 1


def hidden(node):
    return (
        node.tag in SKIP_TEXT
        or "data-burbot-selector-highlight" in node.attrib
        or "data-burbot-picker" in node.attrib
    )


def private_text(node):
    tag = node.tag
    if not isinstance(tag, str):
        return True
    tag = tag.rsplit("}", 1)[-1]
    return (
        hidden(node)
        or tag in PRIVATE_TEXT_TAGS
        or "contenteditable" in node.attrib
        or "data-burbot-import-review-highlight" in node.attrib
        or (tag == "meta" and "http-equiv" in node.attrib)
        or (
            tag == "div"
            and (
                "data-burbot-import-review-focused" in node.attrib
                or node.get("id") == "automa-palette"
            )
        )
    )


def text_nodes(node, excluded=False, *, exclude=hidden):
    if not isinstance(node.tag, str) or node.tag == "template":
        return
    excluded = excluded or exclude(node)
    if node.text:
        yield node.text, excluded
    for child in node:
        yield from text_nodes(child, excluded, exclude=exclude)
        if child.tail:
            yield child.tail, excluded


@dataclass(frozen=True)
class TextIndex:
    text: str
    raw: str
    starts: array
    ends: array

    @classmethod
    def from_element(cls, element):
        raw, normalized = [], []
        starts, ends = array("I"), array("I")
        base = 0
        whitespace = None
        for text, excluded in text_nodes(element, any(hidden(a) for a in element.iterancestors())):
            raw.append(text)
            if not excluded:
                for offset, char in enumerate(text, base):
                    if char in JS_SPACE:
                        if normalized:
                            whitespace = (whitespace[0] if whitespace else offset, offset + 1)
                        continue
                    if whitespace:
                        normalized.append(" ")
                        starts.append(whitespace[0])
                        ends.append(whitespace[1])
                        whitespace = None
                    normalized.append(char)
                    starts.append(offset)
                    ends.append(offset + 1)
            base += len(text)
        return cls("".join(normalized), "".join(raw), starts, ends)

    def fragment(self, start, end):
        return clean(self.raw[self.starts[start] : self.ends[end - 1]])


def quote_matches(index, quote, *, use_context=True):
    exact = clean(quote.exact)
    if not exact:
        return []
    prefix = (quote.prefix or "").rstrip(JS_SPACE) if use_context else ""
    suffix = (quote.suffix or "").lstrip(JS_SPACE) if use_context else ""
    matches = []
    for start in hits(index.text, exact):
        end = start + len(exact)
        # Each whitespace run in the index has already collapsed to one space.
        before = start - (start > 0 and index.text[start - 1] == " ")
        after = end + (end < len(index.text) and index.text[end] == " ")
        if prefix and not index.text.endswith(prefix, 0, before):
            continue
        if suffix and not index.text.startswith(suffix, after):
            continue
        matches.append((start, end))
    return matches


class ExtractionFailure(ValueError):
    def __init__(self, code: ExtractionError, message: str):
        super().__init__(message)
        self.code = code


def boundary_span(text, prefix, suffix):
    starts = list(islice(hits(text, prefix), 201))
    ends = list(islice(hits(text, suffix), 201))
    if len(starts) > 200 or len(ends) > 200:
        return "ambiguous"
    pairs = [
        (start + len(prefix), end) for start in starts for end in ends if end >= start + len(prefix)
    ]
    if len(pairs) != 1:
        return "ambiguous" if pairs else "missing"
    start, end = pairs[0]
    while start < end and text[start] in JS_SPACE:
        start += 1
    while end > start and text[end - 1] in JS_SPACE:
        end -= 1
    return start, end


def selection_matches(index, quote):
    prefix, suffix = clean(quote.prefix or ""), clean(quote.suffix or "")
    if not prefix or not suffix:
        return quote_matches(index, quote, use_context=False)
    span = boundary_span(index.text, prefix, suffix)
    if span == "missing":
        raise ExtractionFailure(
            "selection_context_mismatch", "Selection context no longer matches."
        )
    if span == "ambiguous":
        raise ExtractionFailure("selection_context_ambiguous", "Selection context is ambiguous.")
    if span[0] == span[1]:
        raise ExtractionFailure("empty_value", "Selected text is now empty.")
    return [span]


@dataclass(frozen=True)
class TextRange:
    index: TextIndex
    start: int
    end: int

    def literal(self):
        return self.index.fragment(self.start, self.end)


class HtmlSelectorRuntime:
    """Parse a snapshot locally, without executing scripts or loading resources."""

    def __init__(self, html: bytes | str, page_url: str):
        self.document = html5lib.parse(
            html, treebuilder="lxml", namespaceHTMLElements=False, scripting=True
        )
        self.root = self.document.getroot()
        for template in list(self.root.iter("template")):
            # Browser template contents live in a separate document fragment.
            template.text = None
            del template[:]
        self.body = self.root.find("body")
        self.page_url = page_url
        self._indexes = {}

    @cached_property
    def css(self):
        return ElementWrapper.from_html_root(self.root)

    @cached_property
    def base_url(self):
        base = self.root.find(".//base[@href]")
        if base is None:
            return self.page_url
        try:
            return urljoin(self.page_url, base.get("href"))
        except ValueError:
            return self.page_url

    def index(self, root):
        if root not in self._indexes:
            self._indexes[root] = TextIndex.from_element(root)
        return self._indexes[root]

    def resolve(self, locator):
        match locator.kind:
            case "css_path":
                return [node.etree_element for node in self.css.query_all(locator.selector)]
            case "xpath":
                nodes = etree.XPath(locator.expression, regexp=False)(self.document)
                if not isinstance(nodes, list) or any(
                    not isinstance(node, etree._Element) or not isinstance(node.tag, str)
                    for node in nodes
                ):
                    raise ValueError("XPath must resolve elements.")
                return nodes
            case "element_id":
                return [node for node in self.root.iter() if node.get("id") == locator.element_id]
            case "text_quote":
                index = self.index(self.body if self.body is not None else self.root)
                return [TextRange(index, *span) for span in quote_matches(index, locator.quote)]
            case _:
                return None

    def read_candidate(self, target):
        if isinstance(target, TextRange) or target.tag in {"html", "head", "body"}:
            return None
        if private_text(target) or any(private_text(node) for node in target.iterancestors()):
            return None
        parts = []
        size = 0
        for text, excluded in text_nodes(target, exclude=private_text):
            if excluded:
                continue
            size += utf16_length(text)
            if size > MAX_CANDIDATE_LENGTH:
                return None
            parts.append(text)
        raw = "".join(parts)
        return raw if safe_candidate_text(raw) else None

    def read(self, target, extraction):
        is_range = isinstance(target, TextRange)
        if extraction.type == "attribute":
            if is_range:
                raise ExtractionFailure(
                    "element_required", "Attribute extraction requires an element locator."
                )
            name = extraction.name
            owner = target
            if name == "href":
                owner = next(
                    (
                        element
                        for element in (target, *target.iterancestors())
                        if element.tag == "a" and "href" in element.attrib
                    ),
                    target,
                )
            attribute = owner.get(
                name if owner.tag.startswith("{") else name.translate(HTML_ATTRIBUTE_CASE)
            )
            if attribute is None:
                raise ExtractionFailure(
                    "attribute_missing", "The configured attribute was not found."
                )
            return urljoin(self.base_url, attribute) if name in {"href", "src"} else attribute
        if extraction.type == "text":
            return target.literal() if is_range else self.index(target).text
        if extraction.type == "text_between":
            if is_range:
                raise ExtractionFailure(
                    "element_required", "Text boundaries require an element locator."
                )
            text = self.index(target).text
            span = boundary_span(text, clean(extraction.start), clean(extraction.end))
            if span == "missing":
                raise ExtractionFailure("text_boundary_missing", "Text boundaries no longer match.")
            if span == "ambiguous":
                raise ExtractionFailure(
                    "text_boundary_ambiguous", "Multiple text boundary pairs match."
                )
            return text[span[0] : span[1]]
        if is_range:
            raw = target.literal()
            if raw != clean(extraction.quote.exact):
                raise ExtractionFailure(
                    "selection_quote_mismatch", "Text locator and selection extraction disagree."
                )
            return raw
        index = self.index(target)
        ranges = selection_matches(index, extraction.quote)
        if not ranges:
            raise ExtractionFailure(
                "selection_quote_mismatch", "The selection quote no longer matches."
            )
        if len(ranges) > 1:
            raise ExtractionFailure(
                "selection_quote_ambiguous", "The selection quote matches multiple fragments."
            )
        return index.fragment(*ranges[0])


def failure_status(results):
    return next((s for s in FAILURE_ORDER if any(r.status == s for r in results)), "error")


def evaluate_locator(locator, extraction, runtime):
    identity = {"locator_uuid": locator.uuid}
    try:
        targets = runtime.resolve(locator)
    except Exception as error:
        return LocatorEvaluationResult(
            **identity, match_count=0, status="error", diagnostic=str(error)
        )
    if targets is None:
        return LocatorEvaluationResult(
            **identity,
            match_count=0,
            status="unsupported",
            diagnostic=f"No runtime resolver for {locator.kind}.",
        )
    count = len(targets)
    if count != 1:
        return LocatorEvaluationResult(
            **identity,
            match_count=count,
            status="ambiguous" if count else "not_found",
            diagnostic=f"Locator matched {count} fragments.",
        )
    target = targets[0]
    try:
        raw = runtime.read(target, extraction)
        if not raw:
            raise ExtractionFailure("empty_value", "Extracted value is empty.")
        if utf16_length(raw) > MAX_RAW_LENGTH:
            raise ExtractionFailure("value_too_large", "Extracted value is too large.")
    except Exception as error:
        details = {}
        try:
            observed = runtime.read_candidate(target)
        except Exception:
            observed = None
        if observed is not None:
            details["candidate"] = {
                "raw_text": observed,
                "source": "matched_element_text",
                "verified": False,
            }
        return LocatorEvaluationResult(
            **identity,
            match_count=1,
            status="error",
            diagnostic=str(error),
            extraction_error=error.code
            if isinstance(error, ExtractionFailure)
            else "extraction_failed",
            **details,
        )
    return LocatorEvaluationResult(**identity, match_count=1, status="success", raw_value=raw)


def evaluate_part(part, runtime):
    results = [
        evaluate_locator(locator, part.extraction, runtime) for locator in ordered(part.locators)
    ]
    return summarize_part(part, results)


def summarize_part(part, results):
    base = {"part_uuid": part.uuid, "locator_results": results}
    successes = {result.raw_value for result in results if result.status == "success"}
    if not successes:
        return PartEvaluationResult(
            **base,
            status=failure_status(results),
            diagnostic="No locator resolved this part uniquely.",
        )
    if len(successes) != 1:
        return PartEvaluationResult(
            **base,
            status="conflict",
            diagnostic="Successful locators disagree about this part's value.",
        )
    return PartEvaluationResult(**base, status="success", raw_value=next(iter(successes)))


def evaluate_recipe(recipe, runtime):
    results = [evaluate_part(part, runtime) for part in ordered(recipe.parts)]
    return summarize_recipe(recipe, results)


def summarize_recipe(recipe, results):
    parts = ordered(recipe.parts)
    base = {"recipe_uuid": recipe.uuid, "part_results": results}
    if not results or any(result.status != "success" for result in results):
        return RecipeEvaluationResult(
            **base, status=failure_status(results), diagnostic="Recipe did not produce every part."
        )
    raw = "".join(
        ((part.join_with or "") if index else "") + result.raw_value
        for index, (part, result) in enumerate(zip(parts, results, strict=True))
    )
    if utf16_length(raw) > MAX_RAW_LENGTH:
        return RecipeEvaluationResult(
            **base, status="error", diagnostic="Assembled recipe value is too large."
        )
    return RecipeEvaluationResult(**base, status="success", raw_value=raw)


def evaluate_selector_version(version, runtime):
    results = [evaluate_recipe(recipe, runtime) for recipe in ordered(version.recipes)]
    return summarize_version(version, results)


def summarize_version(version, results):
    base = {"selector_version_uuid": version.uuid, "recipe_results": results}
    successes = {result.raw_value for result in results if result.status == "success"}
    if len(successes) > 1:
        return SelectorEvaluationResult(
            **base, status="conflict", diagnostic="Independent recipes disagree."
        )
    if not results or any(result.status != "success" for result in results):
        return SelectorEvaluationResult(
            **base,
            status=failure_status(results),
            diagnostic="Every independent recipe must produce a complete result.",
        )
    return SelectorEvaluationResult(**base, status="success", raw_value=results[0].raw_value)
