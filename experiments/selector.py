from collections import Counter

from .models import ExperimentCandidate


def utility(candidate: ExperimentCandidate, hypotheses_count: int, execution_cost: float = 1.0) -> float:
    """Transparent active-learning utility: prefer experiments with prediction disagreement."""
    counts = Counter(candidate.predictions.values())
    disagreement = len(counts) / max(hypotheses_count, 1)
    uncertainty = 1.0 - (max(counts.values()) / max(hypotheses_count, 1)) if counts else 0.0
    return round(disagreement + uncertainty + candidate.security_impact - 0.1 * execution_cost - 0.1 * candidate.setup_cost, 4)


def select(candidates: list[ExperimentCandidate], hypotheses_count: int) -> ExperimentCandidate:
    if not candidates:
        raise ValueError("no experiment candidates")
    return max(candidates, key=lambda item: (utility(item, hypotheses_count, item.counterfactual.intervention.cost), item.id))
