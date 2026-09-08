from dataclasses import dataclass, field
import hashlib

from core.models import ExecutionTrace


def trace_fingerprint(trace: ExecutionTrace) -> str:
    value = "|".join(f"{step.probe.actor}:{step.probe.method}:{step.probe.path}:{step.probe.body}" for step in trace.steps)
    return hashlib.sha256(value.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class SearchNode:
    hypothesis_id: str
    seed_trace: ExecutionTrace
    trace: ExecutionTrace
    transformations: tuple[str, ...] = ()
    depth: int = 0
    cost: float = 0.0
    parent_id: str | None = None
    id: str = field(default="")

    @classmethod
    def root(cls, hypothesis_id: str, seed: ExecutionTrace) -> "SearchNode":
        return cls(hypothesis_id, seed, seed, id=f"{hypothesis_id}:root:{trace_fingerprint(seed)}")

    @classmethod
    def child(cls, parent: "SearchNode", trace: ExecutionTrace, operator: object) -> "SearchNode":
        name = getattr(operator, "name", type(operator).__name__)
        transformations = parent.transformations + (name,)
        return cls(parent.hypothesis_id, parent.seed_trace, trace, transformations, parent.depth + 1,
                   parent.cost + sum(step.probe.cost for step in trace.steps), parent.id,
                   f"{parent.hypothesis_id}:{'-'.join(transformations)}:{trace_fingerprint(trace)}")
