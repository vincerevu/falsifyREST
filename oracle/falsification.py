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
    control_provenance: str = "unavailable"
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
        constraints_valid, reason = self._validate_constraints(hypothesis, changed, preserved, context)
        repeat_validation = "occurrence_count" in changed if hypothesis.required_changed_dimensions == {"occurrence_count"} else None
        evidence = OracleEvidence(
            precondition_status=precondition,
            changed_dimensions=frozenset(changed),
            preserved_dimensions=frozenset(preserved),
            preservation_valid=constraints_valid,
            target_identity=treatment_probe.path,
            response_status=response_status,
            protected_fields_disclosed=frozenset({"response"}) if effect.classification == "EFFECTIVE_DISCLOSURE" else frozenset(),
            protected_state_changed=frozenset(effect.changed_fields),
            control_effect=control_effect,
            control_provenance="fresh" if control_effect is not None and context.get("control_is_fresh") else "historical" if control_effect is not None else "unavailable",
            treatment_effect=effect,
            repeat_validation=repeat_validation,
        )
        witness = ContrastiveWitness(hypothesis.id, seed, candidate, tuple(candidate.id.split(":")[1:]),
                                     frozenset(changed), frozenset(preserved), evidence,
                                     "SECURITY_RELEVANT_WITNESS" if constraints_valid and effect.protected_effect else "INCONCLUSIVE")
        if precondition != "DENY":
            return FalsificationVerdict(False, hypothesis.confidence, "treatment did not violate hypothesis precondition", witness, "INCONCLUSIVE")
        if not constraints_valid:
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
        if [step.stable_id for step in seed.steps] != [step.stable_id for step in candidate.steps[:len(seed.steps)]]:
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
    def _context_value(context: dict[str, Any], path: str) -> Any:
        scope, _, field = path.partition(".")
        return context.get(scope, {}).get(field) if field else context.get(scope)

    @classmethod
    def _validate_constraints(cls, hypothesis, changed, preserved, context):
        missing_changes = hypothesis.required_changed_dimensions - changed
        if missing_changes:
            return False, f"missing required changed dimensions: {', '.join(sorted(missing_changes))}"
        if hypothesis.required_any_changed_dimensions and not (hypothesis.required_any_changed_dimensions & changed):
            return False, "none of the alternative required dimensions changed"
        missing_preserved = hypothesis.required_preserved_dimensions - preserved
        if missing_preserved:
            return False, f"missing required preserved dimensions: {', '.join(sorted(missing_preserved))}"
        for path, expected in hypothesis.required_context_values.items():
            if cls._context_value(context, path) != expected:
                return False, f"required context value not met: {path}"
        for left, right in hypothesis.required_distinct_context_fields:
            if cls._context_value(context, left) == cls._context_value(context, right):
                return False, f"required distinct relation not met: {left} != {right}"
        return True, "hypothesis constraints preserved while protected effect occurred"
