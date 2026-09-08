from inference.hypothesis import PolicyHypothesis

from .node import SearchNode


def priority(node: SearchNode, hypothesis: PolicyHypothesis) -> float:
    """Small, inspectable best-first heuristic; larger values are explored first."""
    relevance = 1.0 if node.transformations and all(name in hypothesis.applicable_operators for name in node.transformations) else 0.0
    novelty = 1.0 / (1 + node.depth)
    impact = max(hypothesis.confidence, 0.1)
    return relevance + novelty + impact - 0.1 * node.cost - 0.2 * node.depth
