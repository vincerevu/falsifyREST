from core.models import Probe
from inference.hypothesis import PolicyHypothesis
from violation.counterfactual import CounterfactualExperiment

from .models import ExecutableStep, ExperimentPlan


def compile_counterfactual(experiment: CounterfactualExperiment, hypothesis: PolicyHypothesis) -> ExperimentPlan:
    """Compile known concrete probes; callers resolve setup dependencies from trace evidence."""
    baseline, intervention = experiment.baseline, experiment.intervention
    setup = [ExecutableStep(baseline.id, baseline.actor, baseline.method, baseline.path, purpose="establish valid baseline")]
    target = ExecutableStep(intervention.id, intervention.actor, intervention.method, intervention.path, purpose=f"mutate only {experiment.mutated_condition}")
    observe = ExecutableStep(f"observe-{intervention.id}", "observer", "GET", intervention.path, purpose="capture protected state after intervention")
    return ExperimentPlan(hypothesis.id, setup, target, [observe], experiment.mutated_condition)
