from .hypothesis import PolicyHypothesis


SECURITY_RELEVANCE = {"actor == resource.owner": 1.0, "actor.role == ADMIN": 1.0, "transition": 0.9}


def score(hypothesis: PolicyHypothesis) -> float:
    support_score = min(hypothesis.support / 3, 1.0)
    return round(0.25 * support_score + 0.25 * hypothesis.confidence + 0.30 * SECURITY_RELEVANCE.get(hypothesis.subject_relation, 0.3) + 0.20, 4)


def rank(hypotheses: list[PolicyHypothesis]) -> list[PolicyHypothesis]:
    return sorted(hypotheses, key=score, reverse=True)
