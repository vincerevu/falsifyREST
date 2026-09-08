from core.models import ExecutionTrace, Probe
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


def compile_trace(trace: ExecutionTrace, hypothesis: PolicyHypothesis) -> ExperimentPlan:
    """Compile a complete search-node trace, preserving its workflow order."""
    if not trace.steps:
        raise ValueError("cannot compile an empty execution trace")
    probes = trace.probes
    setup = [ExecutableStep(probe.id, probe.actor, probe.method, probe.path, purpose="replay transformed workflow", probe=probe) for probe in probes[:-1]]
    target_probe = probes[-1]
    target = ExecutableStep(target_probe.id, target_probe.actor, target_probe.method, target_probe.path,
                            purpose="execute transformed target action", probe=target_probe)
    return ExperimentPlan(hypothesis.id, setup, target, [], ", ".join(trace.id.split(":")[1:]))
