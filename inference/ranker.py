from .hypothesis import PolicyHypothesis


SECURITY_RELEVANCE = {"actor == resource.owner": 1.0, "actor.role == ADMIN": 1.0, "transition": 0.9}


def score(hypothesis: PolicyHypothesis) -> float:
    support_score = min(hypothesis.support / 3, 1.0)
    return round(0.25 * support_score + 0.25 * hypothesis.confidence + 0.30 * SECURITY_RELEVANCE.get(hypothesis.subject_relation, 0.3) + 0.20, 4)


def priority_score(hypothesis: PolicyHypothesis, unexplored_state: bool = True, execution_cost: float = 1.0) -> float:
    """Transparent priority function used by the planner, independent of any LLM."""
    novelty = 1.0 if unexplored_state else 0.25
    cost_penalty = min(max(execution_cost, 0.0), 5.0) / 5.0
    return round(score(hypothesis) + 0.15 * novelty - 0.10 * cost_penalty, 4)


def rank(hypotheses: list[PolicyHypothesis]) -> list[PolicyHypothesis]:
    return sorted(hypotheses, key=priority_score, reverse=True)
