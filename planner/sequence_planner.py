from inference.hypothesis import PolicyHypothesis
from inference.ranker import priority_score

from .models import ExperimentStep, PlannedExperiment


def plan_experiments(hypotheses: list[PolicyHypothesis], limit: int | None = None) -> list[PlannedExperiment]:
    """Build reproducible experiment skeletons. Execution is deliberately separate."""
    planned: list[PlannedExperiment] = []
    for hypothesis in hypotheses:
        target = hypothesis.target_operation or hypothesis.action
        if hypothesis.family == "ownership":
            steps = [
                ExperimentStep("actor_a", "create or locate owned resource", target),
                ExperimentStep("actor_b", "repeat operation on actor_a resource", target),
                ExperimentStep("observer", "compare protected effect or disclosure", target),
            ]
        elif hypothesis.family == "replay":
            steps = [
                ExperimentStep("actor_a", "perform action once", target),
                ExperimentStep("actor_a", "replay identical action", target),
                ExperimentStep("observer", "compare protected effect", target),
            ]
        else:
            steps = [
                ExperimentStep("actor_a", "prepare resource lifecycle state", target),
                ExperimentStep("actor_a", "invoke action with unmet transition precondition", target),
                ExperimentStep("observer", "compare protected effect", target),
            ]
        planned.append(PlannedExperiment(hypothesis.id, hypothesis.family, priority_score(hypothesis), steps, "; ".join(hypothesis.preconditions)))
    planned.sort(key=lambda item: item.priority, reverse=True)
    return planned[:limit] if limit is not None else planned
