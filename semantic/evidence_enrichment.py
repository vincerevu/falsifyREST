from evidence.models import Evidence

from .models import APISemanticModel


def enrich_from_evidence(model: APISemanticModel, evidence: list[Evidence]) -> APISemanticModel:
    """Expand semantic candidates only from observed effects; never infer a policy verdict."""
    by_operation = {}
    for semantic in model.operations:
        target = f"{semantic.operation.method} {semantic.operation.path}"
        by_operation.update({semantic.operation.operation_id: semantic, target: semantic})
    for item in evidence:
        semantic = by_operation.get(item.operation_id)
        if semantic is None:
            continue
        changed = [field for field in set(item.pre_state) | set(item.post_state) if item.pre_state.get(field) != item.post_state.get(field)]
        if changed:
            semantic.add_family("state-transition", "evidence", 0.8)
            semantic.state_fields = list(dict.fromkeys([*semantic.state_fields, *sorted(changed)]))
        if item.resource_owner_id or item.actor_relation in {"owner", "foreign"}:
            semantic.add_family("ownership", "evidence", 0.75)
            semantic.relationship_fields = list(dict.fromkeys([*semantic.relationship_fields, "owner_id"]))
    return model
