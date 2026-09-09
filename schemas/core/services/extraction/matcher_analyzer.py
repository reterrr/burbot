# from services.extraction.matchers.pattern_matching_protocol import NodeMatchResults
#
#
# class AnalyzeNodeResults:
#     def __init__(self, results: NodeMatchResults):
#         self._results = results
#
#     @staticmethod
#     def all_true(results: NodeMatchResults) -> NodeMatchResults:
#         return {
#             node: result
#             for node, result in results
#             if type(result) == bool
#         }
#
#     def analyze(self):
#         true_nodes = AnalyzeNodeResults.all_true(self._results)
#         not_true_nodes = {
#             key: value
#             for key, value in self._results.items()
#             if key not in true_nodes
#         }
#
#         for key, value in true_nodes.items():
#
#
#
#
