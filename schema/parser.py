import json
from pathlib import Path
from typing import Any

from .models import Operation


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def load_openapi(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        import yaml  # optional; JSON has no third-party dependency
    except ImportError as error:
        raise ValueError("YAML requires PyYAML; provide a JSON OpenAPI document instead") from error
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_operations(source: str | Path | dict[str, Any]) -> list[Operation]:
    document = load_openapi(source)
    operations = []
    for path, item in document.get("paths", {}).items():
        shared_parameters = item.get("parameters", [])
        for method, definition in item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            content = definition.get("requestBody", {}).get("content", {})
            request_schema = next((value.get("schema", {}) for value in content.values()), {})
            response_schemas = {
                status: next((value.get("schema", {}) for value in response.get("content", {}).values()), {})
                for status, response in definition.get("responses", {}).items()
            }
            operations.append(Operation(
                method=method.upper(), path=path,
                operation_id=definition.get("operationId", f"{method}_{path}"),
                parameters=[*shared_parameters, *definition.get("parameters", [])],
                request_schema=request_schema, response_schemas=response_schemas,
                tags=definition.get("tags", []),
            ))
    return operations
