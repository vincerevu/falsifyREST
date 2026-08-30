from dataclasses import dataclass, field
from typing import Any


@dataclass
class Resource:
    type: str
    id: str
    creator: str | None = None
    owner: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.type}:{self.id}"
