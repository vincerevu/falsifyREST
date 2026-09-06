from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldRef:
    scope: str
    name: str


@dataclass(frozen=True)
class Predicate:
    lhs: FieldRef
    operator: str
    rhs: FieldRef | Any

    def evaluate(self, context: dict[str, dict[str, Any]]) -> bool | None:
        left = context.get(self.lhs.scope, {}).get(self.lhs.name)
        right = context.get(self.rhs.scope, {}).get(self.rhs.name) if isinstance(self.rhs, FieldRef) else self.rhs
        if left is None or right is None:
            return None
        if self.operator == "eq":
            return left == right
        if self.operator == "neq":
            return left != right
        if self.operator == "present":
            return left is not None
        return None
