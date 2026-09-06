from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class StateSnapshot:
    resource_key: str
    fields: dict[str, Any]
    source: str = "response"


class StateSnapshotter:
    """Black-box snapshot interface; adapters supply authorized GET/list lookups."""
    def __init__(self, capture: Callable[[str], dict[str, Any] | None]):
        self.capture = capture

    def take(self, resource_key: str) -> StateSnapshot:
        return StateSnapshot(resource_key, dict(self.capture(resource_key) or {}), "adapter")
