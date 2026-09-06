"""Evidence-gated generic policy-family registry; no handcrafted domain/action rules."""
from abc import ABC, abstractmethod

from evidence.models import Evidence
from semantic.models import APISemanticModel, SemanticOperation

from .hypothesis import PolicyHypothesis
from .predicate import FieldRef, Predicate


def _target(semantic: SemanticOperation) -> str:
    return f"{semantic.operation.method} {semantic.operation.path}"


def _operation_evidence(semantic: SemanticOperation, evidence: list[Evidence]) -> list[Evidence]:
    return [item for item in evidence if item.operation_id in {semantic.operation.operation_id, _target(semantic)}]


class PolicyFamily(ABC):
    name: str

    @abstractmethod
    def instantiate(self, semantic: SemanticOperation, evidence: list[Evidence]) -> list[PolicyHypothesis]:
        """Return hypotheses only when executions provide the required concrete facts."""

    def _common(self, semantic: SemanticOperation) -> dict:
        target = _target(semantic)
        return {"action": target, "target_operation": target, "resource_type": semantic.resource, "resource": semantic.resource,
                "confidence": semantic.family_prior(self.name), "support": 0, "expected": "DENY"}


class OwnershipFamily(PolicyFamily):
    name = "ownership"

    def instantiate(self, semantic: SemanticOperation, evidence: list[Evidence]) -> list[PolicyHypothesis]:
        observations = _operation_evidence(semantic, evidence)
        if not any(item.resource_owner_id or item.actor_relation in {"owner", "foreign"} for item in observations):
            return []
        common = self._common(semantic)
        return [PolicyHypothesis(f"owner-only:{semantic.operation.operation_id}", "actor == resource.owner", family=self.name,
                                 predicates=[Predicate(FieldRef("actor", "id"), "eq", FieldRef("resource", "owner_id"))], **common)]


class AuthorizationFamily(PolicyFamily):
    name = "authorization"

    def instantiate(self, semantic: SemanticOperation, evidence: list[Evidence]) -> list[PolicyHypothesis]:
        if not any(item.actor_id != "anonymous" for item in _operation_evidence(semantic, evidence)):
            return []
        common = self._common(semantic)
        return [PolicyHypothesis(f"authenticated:{semantic.operation.operation_id}", "actor.authenticated", family=self.name,
                                 predicates=[Predicate(FieldRef("actor", "authenticated"), "eq", True)], **common)]


class StateTransitionFamily(PolicyFamily):
    name = "state-transition"

    def instantiate(self, semantic: SemanticOperation, evidence: list[Evidence]) -> list[PolicyHypothesis]:
        observations = [item for item in _operation_evidence(semantic, evidence) if item.outcome == "SUCCESS" and item.pre_state]
        states = {(field, value) for item in observations for field, value in item.pre_state.items() if value is not None}
        common = self._common(semantic)
        return [PolicyHypothesis(f"state:{semantic.operation.operation_id}:{field}:{value}", f"state.{field} == {value}", family=self.name,
                                 predicates=[Predicate(FieldRef("state", field), "eq", value)], **common) for field, value in sorted(states)]


class ReplayFamily(PolicyFamily):
    name = "replay"

    def instantiate(self, semantic: SemanticOperation, evidence: list[Evidence]) -> list[PolicyHypothesis]:
        if not any(item.outcome == "SUCCESS" for item in _operation_evidence(semantic, evidence)):
            return []
        common = self._common(semantic)
        return [PolicyHypothesis(f"single-use:{semantic.operation.operation_id}", "action has not already succeeded", family=self.name,
                                 predicates=[Predicate(FieldRef("history", common["target_operation"]), "eq", False)], **common)]


POLICY_FAMILIES: list[PolicyFamily] = [OwnershipFamily(), AuthorizationFamily(), StateTransitionFamily(), ReplayFamily()]


def generate_candidates(model: APISemanticModel, evidence: list[Evidence] | None = None) -> list[PolicyHypothesis]:
    evidence = evidence or []
    return [hypothesis for semantic in model.operations for family in POLICY_FAMILIES for hypothesis in family.instantiate(semantic, evidence)]
