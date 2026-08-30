from dataclasses import asdict
from typing import Any

from core.models import Probe


class EvoMasterAdapter:
    """Offline adapter: normalize generated EvoMaster actions without modifying EvoMaster."""

    def convert(self, actions: list[dict[str, Any]]) -> list[Probe]:
        probes = []
        for index, action in enumerate(actions):
            probes.append(Probe(
                id=str(action.get("id", f"evomaster_{index}")),
                actor=str(action.get("actor", "anonymous")),
                method=str(action["method"]).upper(),
                path=str(action["path"]),
                body=action.get("body"),
                cost=float(action.get("cost", 1.0)),
                risk=float(action.get("risk", 0.0)),
            ))
        return probes

    @staticmethod
    def serialize(probes: list[Probe]) -> list[dict[str, Any]]:
        return [asdict(probe) for probe in probes]
