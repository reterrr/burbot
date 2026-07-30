from pathlib import Path

from entry.load_rules.common import Rule


class OverallSizeRule(Rule):
    def check(self, path: Path) -> bool:
        ...