from dataclasses import dataclass, field

from inference.hypothesis import PolicyHypothesis


@dataclass
class FeedbackStore:
    attempted: set[str] = field(default_factory=set)
    outcomes: dict[str, str] = field(default_factory=dict)

    def unexplored(self, hypothesis: PolicyHypothesis) -> bool:
        return hypothesis.id not in self.attempted


def apply_result(store: FeedbackStore, hypothesis: PolicyHypothesis, result: str) -> PolicyHypothesis:
    """Update scheduling evidence; verdict still comes from deterministic oracles."""
    store.attempted.add(hypothesis.id)
    store.outcomes[hypothesis.id] = result
    hypothesis.violations_tested += 1
    if result == "COUNTEREXAMPLE":
        hypothesis.status = "CONFIRMED"
        hypothesis.confidence = min(1.0, hypothesis.confidence + 0.2)
    elif result == "POLICY_HOLDS":
        hypothesis.status = "REJECTED"
        hypothesis.confidence = max(0.0, hypothesis.confidence - 0.1)
    else:
        hypothesis.status = "INCONCLUSIVE"
    return hypothesis
