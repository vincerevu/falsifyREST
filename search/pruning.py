from core.models import ExecutionTrace
from inference.hypothesis import PolicyHypothesis

from .node import SearchNode, trace_fingerprint


class SearchPruner:
    def __init__(self, max_depth: int = 2):
        self.max_depth = max_depth
        self._seen: set[str] = set()

    def reject(self, node: SearchNode, hypothesis: PolicyHypothesis) -> bool:
        if node.depth > self.max_depth or not node.trace.steps:
            return True
        fingerprint = trace_fingerprint(node.trace)
        if fingerprint in self._seen:
            return True
        if node.transformations and not hypothesis.is_applicable_operator(node.transformations[-1]):
            return True
        self._seen.add(fingerprint)
        return False
