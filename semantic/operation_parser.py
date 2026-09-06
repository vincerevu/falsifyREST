"""Deterministic OpenAPI fact parser. It intentionally makes no policy-family decision."""
import re

from schema.models import Operation

from .models import APISemanticModel, SemanticOperation


def _literal_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part and not part.startswith("{")]


def _resource_hint(path: str) -> str:
    literals = _literal_parts(path)
    if not literals:
        return "resource"
    tail_is_action_hint = "{" in path and not path.rstrip("/").endswith("}")
    raw = literals[-2] if tail_is_action_hint and len(literals) > 1 else literals[-1]
    value = re.sub(r"[^A-Za-z0-9]", "", raw).lower()
    return value.rstrip("s") or "resource"


def _action_hint(operation: Operation) -> str:
    parts = [part for part in operation.path.split("/") if part]
    if "{" in operation.path and parts and not parts[-1].startswith("{"):
        return re.sub(r"[^A-Za-z0-9]", "", parts[-1]).lower()
    return {"GET": "read", "POST": "create", "PUT": "replace", "PATCH": "update", "DELETE": "delete"}.get(operation.method, "unknown")


def parse_operation_facts(operations: list[Operation]) -> APISemanticModel:
    model = APISemanticModel()
    for operation in operations:
        has_path_id = "{" in operation.path and "}" in operation.path
        parameter_names = [parameter.get("name", "id") for parameter in operation.parameters if parameter.get("in") == "path"]
        model.operations.append(SemanticOperation(
            operation=operation, resource=_resource_hint(operation.path), action=_action_hint(operation),
            static_facts={"method": operation.method, "path": operation.path, "has_path_identifier": has_path_id, "path_parameters": parameter_names},
            actor_fields=["actor.id"], resource_id_fields=parameter_names,
        ))
    return model


infer_semantics = parse_operation_facts
