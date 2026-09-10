from dataclasses import replace

from core.models import ExecutionTrace
from .base import TransformationOperator


class ActorSwap(TransformationOperator):
    name = "actor_swap"
    affected_dimensions = frozenset({"actor", "session"})

    def applicable(self, hypothesis, trace, context) -> bool:
        return bool(trace.steps and getattr(context, "alternate_actor", None))

    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace:
        steps = list(trace.steps)
        target = steps[-1]
        steps[-1] = replace(target, probe=replace(target.probe, id=f"{target.probe.id}:actor-swap", actor=context.alternate_actor))
        return ExecutionTrace(f"{trace.id}:actor-swap", steps)
