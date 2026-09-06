from evidence.context import context_from_evidence
from evidence.models import Evidence

from .hypothesis import PolicyHypothesis


def update_from_evidence(hypotheses: list[PolicyHypothesis], evidence: list[Evidence]) -> list[PolicyHypothesis]:
    """Update support/contradiction from observed outcomes without collapsing alternatives."""
    for hypothesis in hypotheses:
        for item in (entry for entry in evidence if entry.operation_id == hypothesis.target_operation or entry.operation_id == hypothesis.action):
            prediction = hypothesis.predict(context_from_evidence(item).as_dict())
            observed = "ALLOW" if item.outcome == "SUCCESS" else "DENY"
            if prediction == observed:
                if item.id not in hypothesis.support_evidence:
                    hypothesis.support_evidence.append(item.id)
            elif item.id not in hypothesis.contradicting_evidence:
                hypothesis.contradicting_evidence.append(item.id)
        support, contradiction = len(hypothesis.support_evidence), len(hypothesis.contradicting_evidence)
        hypothesis.support = support
        hypothesis.confidence = round((support + 1) / (support + contradiction + 2), 4)
        hypothesis.status = "SUPPORTED" if support > contradiction else "CONTRADICTED" if contradiction > support else "UNRESOLVED"
    return hypotheses
