from dataclasses import dataclass

from core.models import ExecutionTrace
from inference.hypothesis import PolicyHypothesis
from .effect import EffectResult


@dataclass(frozen=True)
class FalsificationVerdict:
    falsified: bool
    confidence: float
    reason: str
    witness: ExecutionTrace | None = None


class FalsificationOracle:
    """Owns the policy decision; search only supplies candidate witnesses."""
    def evaluate(self, hypothesis: PolicyHypothesis, seed: ExecutionTrace, candidate: ExecutionTrace,
                 effect: EffectResult) -> FalsificationVerdict:
        mutation = candidate.id.split(":")[-1]
        if effect.protected_effect:
            return FalsificationVerdict(True, max(hypothesis.confidence, 0.5),
                                        f"protected effect after {mutation}", candidate)
        return FalsificationVerdict(False, hypothesis.confidence, effect.reason)
