from typing import Iterator, Protocol

from entry.adapters.common import RawBatch


class Cleaner(Protocol):
    def clean(self, raw: Iterator[RawBatch]) -> Iterator[RawBatch]:
        ...
