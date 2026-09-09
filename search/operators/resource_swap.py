from dataclasses import replace

from core.models import ExecutionTrace, TraceStep
from .base import TransformationOperator


class ResourceSwap(TransformationOperator):
    name = "resource_swap"
    affected_dimensions = frozenset({"resource"})

    def applicable(self, hypothesis, trace, context) -> bool:
        return bool(trace.steps and getattr(context, "alternate_resource_path", None))

    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace:
        steps = list(trace.steps)
        target = steps[-1]
        steps[-1] = TraceStep(replace(target.probe, id=f"{target.probe.id}:resource-swap", path=context.alternate_resource_path), target.observation, dict(target.bindings))
        return ExecutionTrace(f"{trace.id}:resource-swap", steps)
