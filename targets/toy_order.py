import time

from core.models import Observation, Probe


class ToyOrderTarget:
    """Deterministic target with an intentional manager-approves-draft flaw."""

    def __init__(self):
        self.phase = "draft"
        self.owner = "owner"

    def reset(self) -> None:
        self.phase = "draft"

    def execute(self, probe: Probe) -> Observation:
        if probe.id == "get_order":
            return self._obs(probe, 200, {"id": 1, "status": self.phase})
        if probe.id == "submit_order":
            if probe.actor == self.owner and self.phase == "draft":
                self.phase = "submitted"
                return self._obs(probe, 200, {"id": 1, "status": self.phase})
            return self._obs(probe, 409, {"error": "invalid transition", "status": self.phase})
        if probe.id == "approve_order":
            if probe.actor == "manager" and self.phase in {"draft", "submitted"}:
                self.phase = "approved"
                return self._obs(probe, 200, {"id": 1, "status": self.phase})
            return self._obs(probe, 403, {"error": "forbidden", "status": self.phase})
        return self._obs(probe, 404, {"error": "not found"})

    @staticmethod
    def _obs(probe: Probe, status: int, body: dict) -> Observation:
        return Observation(status, body, {}, probe.actor, probe.method, probe.path, {"order_id": 1}, {"status_field": body.get("status")}, time.time())
