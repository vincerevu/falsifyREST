from inference.hypothesis import PolicyHypothesis

from .feasibility import TraceFeasibilityChecker
from .node import SearchNode, trace_fingerprint


class SearchPruner:
    def __init__(self, max_depth: int = 2):
        self.max_depth = max_depth
        self._seen: set[str] = set()
        self.checker = TraceFeasibilityChecker()
        self.reasons: dict[str, int] = {}

    def reject(self, node: SearchNode, hypothesis: PolicyHypothesis, context: object | None = None) -> bool:
        if node.depth > self.max_depth or not node.trace.steps:
            self._record("depth_or_empty")
            return True
        fingerprint = trace_fingerprint(node.trace)
        if fingerprint in self._seen:
            self._record("duplicate")
            return True
        if node.transformations and not hypothesis.is_applicable_operator(node.transformations[-1]):
            self._record("operator_incompatible")
            return True
        if node.depth and hypothesis.relevant_dimensions and not (node.affected_dimensions & hypothesis.relevant_dimensions):
            self._record("hypothesis_irrelevant")
            return True
        feasibility = self.checker.check(node.trace, context or object())
        if not feasibility.valid:
            self._record(f"infeasible:{feasibility.reason}")
            return True
        self._seen.add(fingerprint)
        return False

    def _record(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1
