from core.models import Probe
from inference.hypothesis import PolicyHypothesis
from violation.counterfactual import CounterfactualExperiment

from .models import ExecutableStep, ExperimentPlan


def compile_counterfactual(experiment: CounterfactualExperiment, hypothesis: PolicyHypothesis) -> ExperimentPlan:
    """Compile known concrete probes; callers resolve setup dependencies from trace evidence."""
    intervention = experiment.intervention
    setup = [ExecutableStep(probe.id, probe.actor, probe.method, probe.path, purpose="establish required counterfactual state", probe=probe) for probe in experiment.setup_probes]
    target = ExecutableStep(intervention.id, intervention.actor, intervention.method, intervention.path, purpose=f"mutate only {experiment.mutated_condition}", probe=intervention)
    observe = [ExecutableStep(probe.id, probe.actor, probe.method, probe.path, purpose="capture protected state after intervention", probe=probe) for probe in experiment.observation_probes]
    return ExperimentPlan(hypothesis.id, setup, target, observe, experiment.mutated_condition)
