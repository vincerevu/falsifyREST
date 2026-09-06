from core.models import Probe
from inference.hypothesis import PolicyHypothesis
from violation.counterfactual import CounterfactualContext, CounterfactualGenerator

from .models import ExperimentCandidate


def generate_counterfactuals(hypotheses: list[PolicyHypothesis], baseline: Probe, context: CounterfactualContext | None = None) -> list[ExperimentCandidate]:
    generator = CounterfactualGenerator()
    context = context or CounterfactualContext()
    candidates = []
    for hypothesis in hypotheses:
        try:
            counterfactual = generator.generate(hypothesis, baseline, context)
        except ValueError:
            continue
        predictions = {other.id: other.predict(counterfactual.context) for other in hypotheses if other.target_operation == hypothesis.target_operation}
        candidates.append(ExperimentCandidate(counterfactual, predictions))
    return candidates
