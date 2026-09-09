from dataclasses import replace

from core.models import ExecutionTrace, TraceStep
from .base import TransformationOperator


class Repeat(TransformationOperator):
    name = "repeat"
    affected_dimensions = frozenset({"history", "occurrence_count"})

    def applicable(self, hypothesis, trace, context) -> bool:
        return bool(trace.steps)

    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace:
        target = trace.steps[-1]
        repeated = TraceStep(replace(target.probe, id=f"{target.probe.id}:repeat"), target.observation, dict(target.bindings))
        return ExecutionTrace(f"{trace.id}:repeat", [*trace.steps, repeated])
