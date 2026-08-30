from copy import deepcopy
from math import log

from .models import Hypothesis, Observation, Prediction, Probe


def normalize(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    total = sum(max(h.weight, 0.0) for h in hypotheses)
    if total:
        for hypothesis in hypotheses:
            hypothesis.weight = max(hypothesis.weight, 0.0) / total
    return hypotheses


def likelihood(predicted: Prediction, observed: Observation) -> float:
    if predicted.status == observed.status:
        return 1.0
    if predicted.status // 100 == observed.status // 100:
        return 0.25
    return 0.05


def update_belief(hypotheses: list[Hypothesis], probe: Probe, observed: Observation, predict) -> list[Hypothesis]:
    for hypothesis in hypotheses:
        predicted = predict(hypothesis, probe)
        hypothesis.weight *= likelihood(predicted, observed)
        observed_phase = observed.features.get("status_field")
        if observed_phase:
            hypothesis.weight *= 3.0 if observed_phase == hypothesis.phase else 0.1
        if predicted.status == observed.status:
            hypothesis.evidence_support.append(f"{probe.id}:{observed.status}")
    return normalize(hypotheses)


def belief_resolved(hypotheses: list[Hypothesis], threshold: float = 0.8) -> bool:
    return bool(hypotheses) and max(h.weight for h in hypotheses) >= threshold


def entropy(hypotheses: list[Hypothesis]) -> float:
    return -sum(h.weight * log(h.weight, 2) for h in hypotheses if h.weight > 0)


def clone_belief(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    return deepcopy(hypotheses)
