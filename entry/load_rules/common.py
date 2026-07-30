from pathlib import Path


class Rule:
    def check(self, path: Path) -> bool:
        ...
