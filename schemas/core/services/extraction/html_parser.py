"""Parse raw HTML into a normalized runtime document."""

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from lxml import html
from lxml.etree import ParserError
from lxml.html import HtmlElement


DEFAULT_MAX_HTML_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_ELEMENTS = 100_000
DEFAULT_MAX_VISIBLE_TEXT_CHARACTERS = 2_000_000


class HtmlParsingError(ValueError):
    """Raised when an HTML document cannot be parsed."""


class HtmlLimitExceededError(HtmlParsingError):
    """Raised when an HTML document exceeds configured limits."""


@dataclass(frozen=True, slots=True)
class ParsedHtmlElement:
    """Represent one runtime HTML element.

    ``id`` is local to the parsed document. It is not yet the database
    identifier from the ``elements`` table.
    """

    id: int
    parent_id: int | None
    dom_order: int
    tag_name: str
    xpath: str
    attributes: Mapping[str, str]

    node: HtmlElement = field(
        repr=False,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class ParsedTextFragment:
    """Represent one visible text fragment owned by a DOM element."""

    id: int
    element_id: int
    order: int

    raw_text: str
    normalized_text: str


@dataclass(frozen=True, slots=True)
class ParsedHtmlDocument:
    """Represent parsed and normalized HTML."""

    url: str
    root_element_id: int

    elements: tuple[ParsedHtmlElement, ...]
    text_fragments: tuple[ParsedTextFragment, ...]
    visible_text: str

    elements_by_id: Mapping[int, ParsedHtmlElement] = field(
        repr=False,
        compare=False,
    )

    @property
    def element_count(self) -> int:
        """Return the number of analyzed DOM elements."""

        return len(self.elements)

    def get_element(self, element_id: int) -> ParsedHtmlElement:
        """Return a parsed element by its runtime identifier."""

        try:
            return self.elements_by_id[element_id]
        except KeyError as error:
            raise KeyError(
                f"Parsed HTML element {element_id} does not exist."
            ) from error


class HtmlParser:
    """Parse HTML into elements and ordered visible text fragments."""

    IGNORED_TAGS = frozenset(
        {
            "script",
            "style",
            "noscript",
            "template",
            "svg",
            "canvas",
            "iframe",
            "object",
        }
    )

    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _DISPLAY_NONE_PATTERN = re.compile(
        r"(?:^|;)\s*display\s*:\s*none(?:\s*!important)?\s*(?:;|$)",
        re.IGNORECASE,
    )
    _VISIBILITY_HIDDEN_PATTERN = re.compile(
        r"(?:^|;)\s*visibility\s*:\s*hidden"
        r"(?:\s*!important)?\s*(?:;|$)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
        max_elements: int = DEFAULT_MAX_ELEMENTS,
        max_visible_text_characters: int = (
            DEFAULT_MAX_VISIBLE_TEXT_CHARACTERS
        ),
    ) -> None:
        if max_html_bytes <= 0:
            raise ValueError("max_html_bytes must be positive.")

        if max_elements <= 0:
            raise ValueError("max_elements must be positive.")

        if max_visible_text_characters <= 0:
            raise ValueError(
                "max_visible_text_characters must be positive."
            )

        self._max_html_bytes = max_html_bytes
        self._max_elements = max_elements
        self._max_visible_text_characters = (
            max_visible_text_characters
        )

    def parse(
        self,
        *,
        url: str,
        html_string: str,
    ) -> ParsedHtmlDocument:
        """Parse and normalize one HTML document.

        :param url: Source URL used as the document base URL.
        :param html_string: Raw HTML document.
        :return: Parsed runtime HTML document.
        :raises HtmlParsingError: If the document cannot be parsed.
        :raises HtmlLimitExceededError: If configured limits are exceeded.
        """

        self._validate_html(html_string)

        parser = html.HTMLParser(
            encoding="utf-8",
            remove_comments=True,
            recover=True,
            huge_tree=False,
        )

        try:
            document_root = html.document_fromstring(
                html_string,
                parser=parser,
                base_url=url,
            )
        except (ParserError, TypeError, ValueError) as error:
            raise HtmlParsingError(
                f"Could not parse HTML document from {url!r}."
            ) from error

        analysis_root = self._find_analysis_root(document_root)
        self._remove_ignored_elements(analysis_root)

        tree = analysis_root.getroottree()

        elements: list[ParsedHtmlElement] = []
        text_fragments: list[ParsedTextFragment] = []
        elements_by_id: dict[int, ParsedHtmlElement] = {}

        visible_character_count = 0
        next_element_id = 1
        next_fragment_id = 1
        next_fragment_order = 0

        def append_fragment(
            *,
            owner_element_id: int,
            raw_text: str | None,
        ) -> None:
            nonlocal visible_character_count
            nonlocal next_fragment_id
            nonlocal next_fragment_order

            if not raw_text:
                return

            normalized_text = self._normalize_text(raw_text)

            if not normalized_text:
                return

            visible_character_count += len(normalized_text)

            if (
                visible_character_count
                > self._max_visible_text_characters
            ):
                raise HtmlLimitExceededError(
                    "Visible text exceeds "
                    f"{self._max_visible_text_characters} characters."
                )

            text_fragments.append(
                ParsedTextFragment(
                    id=next_fragment_id,
                    element_id=owner_element_id,
                    order=next_fragment_order,
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                )
            )

            next_fragment_id += 1
            next_fragment_order += 1

        def visit(
            node: HtmlElement,
            *,
            parent_element_id: int | None,
        ) -> None:
            nonlocal next_element_id

            if not isinstance(node.tag, str):
                return

            if self._is_hidden(node):
                return

            if len(elements) >= self._max_elements:
                raise HtmlLimitExceededError(
                    f"DOM exceeds {self._max_elements} analyzed elements."
                )

            element_id = next_element_id
            next_element_id += 1

            parsed_element = ParsedHtmlElement(
                id=element_id,
                parent_id=parent_element_id,
                dom_order=len(elements),
                tag_name=node.tag.lower(),
                xpath=tree.getpath(node),
                attributes=MappingProxyType(
                    {
                        str(name): str(value)
                        for name, value in node.attrib.items()
                    }
                ),
                node=node,
            )

            elements.append(parsed_element)
            elements_by_id[element_id] = parsed_element

            # Text before the first child belongs to the current element.
            append_fragment(
                owner_element_id=element_id,
                raw_text=node.text,
            )

            for child in node:
                if isinstance(child, HtmlElement):
                    visit(
                        child,
                        parent_element_id=element_id,
                    )

                # Tail occurs after the child but belongs structurally
                # to the current element.
                append_fragment(
                    owner_element_id=element_id,
                    raw_text=child.tail,
                )

        visit(
            analysis_root,
            parent_element_id=None,
        )

        if not elements:
            raise HtmlParsingError(
                "HTML document does not contain analyzable elements."
            )

        visible_text = "\n".join(
            fragment.normalized_text
            for fragment in text_fragments
        )

        return ParsedHtmlDocument(
            url=url,
            root_element_id=elements[0].id,
            elements=tuple(elements),
            text_fragments=tuple(text_fragments),
            visible_text=visible_text,
            elements_by_id=MappingProxyType(elements_by_id),
        )

    def _validate_html(self, html_string: str) -> None:
        if not html_string.strip():
            raise HtmlParsingError("HTML document is empty.")

        # A UTF-8 character requires at least one byte. This avoids
        # unnecessarily encoding obviously oversized documents.
        if len(html_string) > self._max_html_bytes:
            raise HtmlLimitExceededError(
                f"HTML exceeds {self._max_html_bytes} bytes."
            )

        html_size = len(html_string.encode("utf-8"))

        if html_size > self._max_html_bytes:
            raise HtmlLimitExceededError(
                f"HTML size is {html_size} bytes; "
                f"limit is {self._max_html_bytes} bytes."
            )

    @staticmethod
    def _find_analysis_root(
        document_root: HtmlElement,
    ) -> HtmlElement:
        body = document_root.find("body")
        return body if body is not None else document_root

    def _remove_ignored_elements(
        self,
        root: HtmlElement,
    ) -> None:
        ignored_xpath = " | ".join(
            f".//{tag}"
            for tag in sorted(self.IGNORED_TAGS)
        )

        if not ignored_xpath:
            return

        for element in root.xpath(ignored_xpath):
            element.drop_tree()

    def _is_hidden(self, element: HtmlElement) -> bool:
        if "hidden" in element.attrib:
            return True

        if "inert" in element.attrib:
            return True

        if element.attrib.get("aria-hidden", "").casefold() == "true":
            return True

        if (
            element.tag.casefold() == "input"
            and element.attrib.get("type", "").casefold() == "hidden"
        ):
            return True

        style = element.attrib.get("style", "")

        return bool(
            self._DISPLAY_NONE_PATTERN.search(style)
            or self._VISIBILITY_HIDDEN_PATTERN.search(style)
        )

    def _normalize_text(self, value: str) -> str:
        return self._WHITESPACE_PATTERN.sub(" ", value).strip()