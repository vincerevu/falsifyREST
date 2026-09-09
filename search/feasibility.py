from dataclasses import dataclass, field

from core.models import ExecutionTrace


@dataclass(frozen=True)
class FeasibilityResult:
    valid: bool
    reason: str = "valid"
    unresolved_bindings: frozenset[str] = field(default_factory=frozenset)


class TraceFeasibilityChecker:
    """Enforces that a treatment trace remains executable after intervention."""
    def check(self, trace: ExecutionTrace, context: object) -> FeasibilityResult:
        available = set(getattr(context, "initial_bindings", set()))
        sessions = getattr(context, "actor_sessions", {})
        for step in trace.steps:
            if sessions and not sessions.get(step.probe.actor, False):
                return FeasibilityResult(False, f"no usable session for actor {step.probe.actor}")
            missing = set(step.consumes) - available
            if missing:
                return FeasibilityResult(False, "unresolved trace bindings", frozenset(missing))
            available.update(step.produces)
        return FeasibilityResult(True)
