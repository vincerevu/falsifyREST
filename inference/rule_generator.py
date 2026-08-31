"""Deterministic hypothesis templates derived from API semantics and observations."""
from semantic.models import APISemanticModel

from .hypothesis import PolicyHypothesis


def generate_rule_hypotheses(model: APISemanticModel) -> list[PolicyHypothesis]:
    """Generate candidates only. This function never determines whether a policy holds."""
    candidates: list[PolicyHypothesis] = []
    for semantic in model.operations:
        operation = semantic.operation
        target = f"{operation.method} {operation.path}"
        common = {
            "action": target,
            "resource_type": semantic.resource,
            "resource": semantic.resource,
            "target_operation": target,
            "confidence": semantic.confidence,
            "support": 1,
            "evidence": list(semantic.likely_invariants),
        }
        if "ownership" in semantic.security_concepts:
            candidates.append(PolicyHypothesis(
                id=f"ownership:{operation.operation_id}",
                subject_relation="actor == resource.owner",
                preconditions=["resource exists", "actor differs from resource.owner"],
                family="ownership",
                **common,
            ))
        if "state-transition" in semantic.security_concepts:
            candidates.append(PolicyHypothesis(
                id=f"state:{operation.operation_id}",
                subject_relation="transition",
                preconditions=["resource exists", "transition precondition is unmet"],
                family="state-transition",
                **common,
            ))
        if "replay" in semantic.security_concepts:
            candidates.append(PolicyHypothesis(
                id=f"replay:{operation.operation_id}",
                subject_relation="same request is single-use",
                preconditions=["resource exists", "identical action was already accepted"],
                family="replay",
                **common,
            ))
    return candidates
