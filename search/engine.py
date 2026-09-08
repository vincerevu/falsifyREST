from collections.abc import Callable
from dataclasses import dataclass, field

from inference.hypothesis import PolicyHypothesis

from .frontier import BestFirstFrontier
from .node import SearchNode
from .pruning import SearchPruner
from .scoring import priority


@dataclass
class SearchResult:
    counterexample: SearchNode | None = None
    evaluated: list[SearchNode] = field(default_factory=list)


class CounterexampleSearchEngine:
    """Best-first counterexample search over transformed execution traces."""
    def __init__(self, operators: list[object], max_depth: int = 2):
        self.operators = operators
        self.max_depth = max_depth

    def search(self, hypothesis: PolicyHypothesis, seed, budget: int, context: object,
               evaluate: Callable[[SearchNode], bool]) -> SearchResult:
        frontier, pruner, result = BestFirstFrontier(), SearchPruner(self.max_depth), SearchResult()
        root = SearchNode.root(hypothesis.id, seed)
        # The successful seed establishes the workflow; only mutations are executed as tests.
        pruner.reject(root, hypothesis)
        frontier.push(root, priority(root, hypothesis))
        while frontier and len(result.evaluated) < budget:
            node = frontier.pop()
            if node.depth >= self.max_depth:
                continue
            for operator in self.operators:
                if len(result.evaluated) >= budget or not hypothesis.is_applicable_operator(operator):
                    continue
                if not operator.applicable(hypothesis, node.trace, context):
                    continue
                child = SearchNode.child(node, operator.apply(node.trace, context), operator)
                if pruner.reject(child, hypothesis):
                    continue
                result.evaluated.append(child)
                if evaluate(child):
                    result.counterexample = child
                    return result
                frontier.push(child, priority(child, hypothesis))
        return result
