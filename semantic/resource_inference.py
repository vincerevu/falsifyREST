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
    candidate = parts[-1] if parts[-1] not in STATEFUL_ACTIONS else (parts[-2] if len(parts) > 1 else parts[-1])
    candidate = re.sub(r"[^A-Za-z0-9]", "", candidate).lower()
    return candidate.rstrip("s") or "resource"


def _action(operation: Operation) -> str:
    tokens = [token.lower() for token in re.split(r"[/{}_-]+", operation.path) if token]
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
        if "{" in operation.path and "}" in operation.path:
            concepts.add("ownership")
            invariants.append(f"only owner may {action} {resource}")
        if action in STATEFUL_ACTIONS:
            concepts.add("state-transition")
            invariants.append(f"{action} requires a valid {resource} state")
        if action in REPLAY_ACTIONS and operation.method in WRITE_METHODS:
            concepts.add("replay")
            invariants.append(f"{action} should not be effective when replayed")
        families = set(concepts)
        model.operations.append(SemanticOperation(operation, resource, action, concepts, invariants, 0.55, "rule",
            actor_fields=["actor.id"], resource_id_fields=[parameter.get("name", "id") for parameter in operation.parameters if parameter.get("in") == "path"],
            state_fields=["status"] if action in STATEFUL_ACTIONS else [], relationship_fields=["owner_id"] if "ownership" in concepts else [], candidate_policy_families=families))
    return model
