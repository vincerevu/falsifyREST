from dataclasses import dataclass, field
from typing import Any

from core.models import ExecutionTrace
from inference.hypothesis import PolicyHypothesis

from .effect import EffectResult


@dataclass(frozen=True)
class OracleEvidence:
    """Machine-readable validation record for a controlled treatment."""
    precondition_status: str
    changed_dimensions: frozenset[str]
    preserved_dimensions: frozenset[str]
    preservation_valid: bool
    target_identity: str | None
    response_status: int | None
    protected_fields_disclosed: frozenset[str] = field(default_factory=frozenset)
    protected_state_changed: frozenset[str] = field(default_factory=frozenset)
    control_effect: EffectResult | None = None
    treatment_effect: EffectResult | None = None
    repeat_validation: bool | None = None


@dataclass(frozen=True)
class ContrastiveWitness:
    hypothesis_id: str
    control: ExecutionTrace
    treatment: ExecutionTrace
    intervention: tuple[str, ...]
    changed_dimensions: frozenset[str]
    preserved_dimensions: frozenset[str]
    oracle_evidence: OracleEvidence
    validation_status: str


@dataclass(frozen=True)
class FalsificationVerdict:
    falsified: bool
    confidence: float
    reason: str
    witness: ContrastiveWitness | None = None
    classification: str = "NOT_FALSIFIED_WITHIN_BUDGET"


class FalsificationOracle:
    """Validates relation-preserving control/treatment security experiments."""
    def evaluate(self, hypothesis: PolicyHypothesis, seed: ExecutionTrace, candidate: ExecutionTrace,
                 effect: EffectResult, context: dict[str, Any] | None = None,
                 control_effect: EffectResult | None = None, response_status: int | None = None) -> FalsificationVerdict:
        context = context or {}
        control_probe, treatment_probe = seed.probes[-1], candidate.probes[-1]
        changed = self._changed_dimensions(seed, candidate)
        preserved = self._preserved_dimensions(control_probe, treatment_probe)
        precondition = hypothesis.predict(context)
        family_valid, reason, repeat_validation = self._family_valid(
            hypothesis, seed, candidate, changed, preserved, context,
        )
        evidence = OracleEvidence(
            precondition_status=precondition,
            changed_dimensions=frozenset(changed),
            preserved_dimensions=frozenset(preserved),
            preservation_valid=family_valid,
            target_identity=treatment_probe.path,
            response_status=response_status,
            protected_fields_disclosed=frozenset({"response"}) if effect.classification == "EFFECTIVE_DISCLOSURE" else frozenset(),
            protected_state_changed=frozenset(effect.changed_fields),
            control_effect=control_effect,
            treatment_effect=effect,
            repeat_validation=repeat_validation,
        )
        witness = ContrastiveWitness(hypothesis.id, seed, candidate, tuple(candidate.id.split(":")[1:]),
                                     frozenset(changed), frozenset(preserved), evidence,
                                     "SECURITY_RELEVANT_WITNESS" if family_valid and effect.protected_effect else "INCONCLUSIVE")
        if precondition != "DENY":
            return FalsificationVerdict(False, hypothesis.confidence, "treatment did not violate hypothesis precondition", witness, "INCONCLUSIVE")
        if not family_valid:
            return FalsificationVerdict(False, hypothesis.confidence, reason, witness, "INCONCLUSIVE")
        if not effect.protected_effect:
            return FalsificationVerdict(False, hypothesis.confidence, effect.reason, witness, "NOT_FALSIFIED_WITHIN_BUDGET")
        return FalsificationVerdict(True, max(hypothesis.confidence, 0.5), reason, witness, "SECURITY_RELEVANT_WITNESS")

    @staticmethod
    def _changed_dimensions(seed: ExecutionTrace, candidate: ExecutionTrace) -> set[str]:
        control, treatment = seed.probes[-1], candidate.probes[-1]
        changed = set()
        if control.actor != treatment.actor:
            changed.add("actor")
        if control.path != treatment.path:
            changed.add("resource")
        if control.method != treatment.method or control.body != treatment.body:
            changed.add("request_shape")
        if len(seed.steps) != len(candidate.steps):
            changed.add("occurrence_count" if len(candidate.steps) > len(seed.steps) else "sequence")
        if [step.probe.id for step in seed.steps] != [step.probe.id for step in candidate.steps[:len(seed.steps)]]:
            changed.add("order")
        return changed

    @staticmethod
    def _preserved_dimensions(control, treatment) -> set[str]:
        preserved = set()
        if control.method == treatment.method:
            preserved.add("operation")
        if control.path == treatment.path:
            preserved.add("resource")
        if control.body == treatment.body:
            preserved.add("request_shape")
        return preserved

    @staticmethod
    def _family_valid(hypothesis, seed, candidate, changed, preserved, context):
        actor = context.get("actor", {})
        resource = context.get("resource", {})
        if hypothesis.family == "ownership":
            valid = "actor" in changed and "resource" in preserved and actor.get("id") != resource.get("owner_id")
            return valid, "ownership relation was not changed as required" if not valid else "foreign actor produced protected effect", None
        if hypothesis.family == "authorization":
            valid = "actor" in changed and "operation" in preserved
            return valid, "authorization context or operation was not changed as required" if not valid else "unprivileged actor produced protected effect", None
        if hypothesis.family == "state-transition":
            valid = bool(changed & {"sequence", "order"}) and "operation" in preserved
            return valid, "state prerequisite/order was not changed as required" if not valid else "invalid workflow produced protected effect", None
        if hypothesis.family == "replay":
            valid = "occurrence_count" in changed and len(candidate.steps) >= len(seed.steps) + 1
            return valid, "replay was not a second equivalent action" if not valid else "repeated action produced protected effect", valid
        valid = bool(changed & hypothesis.relevant_dimensions) and "operation" in preserved
        return valid, "treatment is not hypothesis-relevant" if not valid else "relevant treatment produced protected effect", None
