import re

from schema.models import Operation
from .models import APISemanticModel, SemanticOperation


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
STATEFUL_ACTIONS = {"approve", "cancel", "checkout", "pay", "refund", "ship", "submit", "redeem"}
REPLAY_ACTIONS = {"checkout", "pay", "refund", "redeem", "transfer", "submit"}


def _resource_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part and not part.startswith("{")]
    if not parts:
        return "resource"
    has_resource_id = "{" in path and "}" in path
    candidate = parts[-2] if has_resource_id and len(parts) > 1 and not path.rstrip("/").endswith("}") else parts[-1]
    candidate = re.sub(r"[^A-Za-z0-9]", "", candidate).lower()
    return candidate.rstrip("s") or "resource"


def _action(operation: Operation) -> str:
    tokens = [token.lower() for token in re.split(r"[/{}_-]+", operation.path) if token]
    path_parts = [part for part in operation.path.split("/") if part]
    if "{" in operation.path and path_parts and not path_parts[-1].startswith("{"):
        return re.sub(r"[^A-Za-z0-9]", "", path_parts[-1]).lower()
    known = next((token for token in reversed(tokens) if token in STATEFUL_ACTIONS), None)
    if known:
        return known
    return {"GET": "read", "POST": "create", "PUT": "modify", "PATCH": "modify", "DELETE": "delete"}.get(operation.method, "unknown")


def infer_semantics(operations: list[Operation]) -> APISemanticModel:
    model = APISemanticModel()
    for operation in operations:
        resource, action = _resource_from_path(operation.path), _action(operation)
        concepts = set()
        invariants = []
        has_resource_id = "{" in operation.path and "}" in operation.path
        targets_existing_resource = has_resource_id and operation.method in WRITE_METHODS
        semantic = SemanticOperation(operation, resource, action, concepts, invariants, 0.45, "rule",
            actor_fields=["actor.id"], resource_id_fields=[parameter.get("name", "id") for parameter in operation.parameters if parameter.get("in") == "path"])
        if has_resource_id:
            concepts.add("ownership")
            invariants.append(f"only owner may {action} {resource}")
            semantic.add_family("ownership", "rule", 0.55)
        if targets_existing_resource:
            concepts.add("state-transition")
            invariants.append(f"{action} requires a valid {resource} state")
            semantic.add_family("state-transition", "rule", 0.55 + (0.2 if action in STATEFUL_ACTIONS else 0.0))
        if operation.method in {"POST", "PATCH"}:
            concepts.add("replay")
            invariants.append(f"{action} should not be effective when replayed")
            semantic.add_family("replay", "rule", 0.45 + (0.2 if action in REPLAY_ACTIONS else 0.0))
        semantic.security_concepts.update(concepts)
        semantic.likely_invariants.extend(invariants)
        if "ownership" in concepts:
            semantic.relationship_fields.append("owner_id")
        model.operations.append(semantic)
    return model
