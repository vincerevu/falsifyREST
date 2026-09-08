from core.models import ExecutionTrace
from .base import TransformationOperator


class OmitStep(TransformationOperator):
    name = "omit_step"

    def applicable(self, hypothesis, trace, context) -> bool:
        return len(trace.steps) > 1

    def apply(self, trace: ExecutionTrace, context: object) -> ExecutionTrace:
        # Retain the target action (the last step), omitting its immediate prerequisite.
        return ExecutionTrace(f"{trace.id}:omit", [*trace.steps[:-2], trace.steps[-1]])
