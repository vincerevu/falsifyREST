from dataclasses import dataclass, field

from inference.hypothesis import PolicyHypothesis


@dataclass
class FeedbackStore:
    attempted: set[str] = field(default_factory=set)
    outcomes: dict[str, str] = field(default_factory=dict)

    def unexplored(self, hypothesis: PolicyHypothesis) -> bool:
        return hypothesis.id not in self.attempted


def apply_result(store: FeedbackStore, hypothesis: PolicyHypothesis, result: str) -> PolicyHypothesis:
    """Compatibility update for externally classified results."""
    store.attempted.add(hypothesis.id)
    store.outcomes[hypothesis.id] = result
    hypothesis.violations_tested += 1
    if result == "COUNTEREXAMPLE":
        hypothesis.contradicting_evidence.append(f"oracle:{hypothesis.violations_tested}")
    elif result == "POLICY_HOLDS":
        hypothesis.support_evidence.append(f"oracle:{hypothesis.violations_tested}")
    hypothesis.confidence = round((len(hypothesis.support_evidence) + 1) / (len(hypothesis.support_evidence) + len(hypothesis.contradicting_evidence) + 2), 4)
    hypothesis.status = "CONFIRMED" if result == "COUNTEREXAMPLE" else "SUPPORTED" if result == "POLICY_HOLDS" else "INCONCLUSIVE"
    return hypothesis
