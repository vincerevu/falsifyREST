from semantic.models import APISemanticModel

from .hypothesis import PolicyHypothesis
from .predicate import FieldRef, Predicate


def generate_candidates(model: APISemanticModel) -> list[PolicyHypothesis]:
    """Instantiate alternatives to test, never policy facts inferred from endpoint names."""
    candidates: list[PolicyHypothesis] = []
    for semantic in model.operations:
        op = semantic.operation
        target = f"{op.method} {op.path}"
        common = dict(action=target, target_operation=target, resource_type=semantic.resource, resource=semantic.resource,
                      confidence=0.5, support=0, expected="DENY", evidence=list(semantic.likely_invariants))
        if "ownership" in semantic.candidate_policy_families:
            candidates.extend([
                PolicyHypothesis(f"owner-only:{op.operation_id}", "actor == resource.owner", family="ownership", predicates=[Predicate(FieldRef("actor", "id"), "eq", FieldRef("resource", "owner_id"))], **common),
                PolicyHypothesis(f"authenticated:{op.operation_id}", "actor.authenticated", family="authorization", predicates=[Predicate(FieldRef("actor", "authenticated"), "eq", True)], **common),
            ])
        if "state-transition" in semantic.candidate_policy_families:
            candidates.append(PolicyHypothesis(f"state-required:{op.operation_id}", "state precondition", family="state-transition", **common))
        if "replay" in semantic.candidate_policy_families:
            candidates.append(PolicyHypothesis(f"single-use:{op.operation_id}", "action has not already succeeded", family="replay", **common))
    return candidates
