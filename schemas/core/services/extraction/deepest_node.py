from services.extraction.matchers.pattern_matching_protocol import NodeMatchResults, MatchResult


class FindDeepestNode:
    def __init__(self, matches: NodeMatchResults):
        self._matches = matches

    def __call__(self) -> MatchResult:
        result = MatchResult()



        return result
