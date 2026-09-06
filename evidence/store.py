from .models import Evidence


class EvidenceStore:
    def __init__(self, evidence: list[Evidence] | None = None):
        self._evidence = list(evidence or [])

    def add(self, item: Evidence) -> None:
        self._evidence.append(item)

    def all(self) -> list[Evidence]:
        return list(self._evidence)

    def for_operation(self, operation_id: str) -> list[Evidence]:
        return [item for item in self._evidence if item.operation_id == operation_id]
