import re
from dataclasses import field, dataclass

from db import TokenClass
from repositories import TokenClassRepository


@dataclass(slots=True)
class EvidenceToken:
    raw: str
    normalized: str

    index: int

    start: int
    end: int

    classes: set[TokenClass] = field(default_factory=set)


class EvidenceBuilder:
    def __init__(
            self,
            repository: TokenClassRepository,
    ) -> None:
        self._repository = repository

    async def build(
            self,
            text: str,
    ) -> list[EvidenceToken]:
        result: list[EvidenceToken] = []

        token_classes = await self._repository.list()

        for index, match in enumerate(re.finditer(r"\S+", text)):
            raw = match.group()

            token = EvidenceToken(
                raw=raw,
                normalized=self._normalize(raw),
                index=index,
                start=match.start(),
                end=match.end(),
                classes=self._resolve_token_classes(
                    self._normalize(raw),
                    token_classes,
                ),
            )

            result.append(token)

        return result

    @staticmethod
    def _normalize(
            text: str,
    ) -> str:
        return text.strip().lower()

    @staticmethod
    def _matches(token_class: TokenClass, token: str):
        if token_class.validation_regex is None:
            return False

        return re.fullmatch(
            token_class.validation_regex,
            token,
        ) is not None

    @staticmethod
    def _resolve_token_classes(
            token: str,
            token_classes: list[TokenClass],
    ) -> set[TokenClass]:
        result: set[TokenClass] = set()

        for token_class in token_classes:
            if EvidenceBuilder._matches(token_class, token):
                result.add(
                    token_class
                )

        return result
