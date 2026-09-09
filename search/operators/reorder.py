from core.models import ExecutionTrace

from .base import TransformationOperator


class Reorder(TransformationOperator):
    """Swap two prerequisites while preserving the final target action."""
    name = "reorder"
    affected_dimensions = frozenset({"order", "sequence"})

    def applicable(self, hypothesis, trace, context) -> bool:
        if len(trace.steps) < 3:
            return False
        first, second = trace.steps[-3:-1]
        # A producer cannot move after a consumer that needs its output.
        return not (first.produces & second.consumes)

    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace:
        return ExecutionTrace(f"{trace.id}:reorder", [*trace.steps[:-3], trace.steps[-2], trace.steps[-3], trace.steps[-1]])
