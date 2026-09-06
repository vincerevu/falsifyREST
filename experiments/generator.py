from core.models import Probe
from inference.hypothesis import PolicyHypothesis
from violation import CounterfactualGenerator

from .models import ExperimentCandidate


def generate_counterfactuals(hypotheses: list[PolicyHypothesis], baseline: Probe, alternate_actor: str | None = None) -> list[ExperimentCandidate]:
    generator = CounterfactualGenerator()
    candidates = []
    for hypothesis in hypotheses:
        try:
            counterfactual = generator.generate(hypothesis, baseline, alternate_actor)
        except ValueError:
            continue
        context = {"actor": {"id": counterfactual.intervention.actor, "authenticated": counterfactual.intervention.actor != "anonymous"}, "resource": {}, "state": {}}
        predictions = {other.id: other.predict(context) for other in hypotheses if other.target_operation == hypothesis.target_operation}
        candidates.append(ExperimentCandidate(counterfactual, predictions))
    return candidates
