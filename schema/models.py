from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    operation_id: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_schema: dict[str, Any] = field(default_factory=dict)
    response_schemas: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
