from core.models import ExecutionTrace
from inference.hypothesis import PolicyHypothesis


class SeedSelector:
    """Choose short observed successful workflows instead of fabricating a family plan."""
    def select(self, hypothesis: PolicyHypothesis, traces: list[ExecutionTrace]) -> list[ExecutionTrace]:
        supported = [trace for trace in traces if not hypothesis.supporting_trace_ids or trace.id in hypothesis.supporting_trace_ids]
        return sorted(supported or traces, key=lambda trace: (len(trace.steps), trace.id))
