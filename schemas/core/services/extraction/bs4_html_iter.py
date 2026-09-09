from enum import Enum
from typing import Iterator

from bs4 import Tag


class TokenClassType(Enum):
    WORD = "WORD"
    IDENTIFIER = "IDENTIFIER"

    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    PERCENTAGE = "PERCENTAGE"

    CURRENCY = "CURRENCY"

    DATE = "DATE"
    YEAR = "YEAR"
    TIME = "TIME"

    EMAIL = "EMAIL"
    URL = "URL"
    PHONE = "PHONE"

    POSTAL_CODE = "POSTAL_CODE"

    BOOLEAN = "BOOLEAN"


class HtmlIterator:
    def __init__(self, node: Tag) -> None:
        self._root = node

    def __iter__(self) -> Iterator[Tag]:
        stack = [self._root]

        while stack:
            node = stack.pop()
            yield node

            children = [
                child
                for child in node.children
                if isinstance(child, Tag)
            ]

            # Preserve the original HTML order.
            stack.extend(reversed(children))
