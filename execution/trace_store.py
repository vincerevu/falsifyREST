import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.models import Observation


@dataclass
class Trace:
    observations: list[Observation] = field(default_factory=list)

    def append(self, observation: Observation) -> None:
        self.observations.append(observation)

    def by_endpoint(self, endpoint: str) -> list[Observation]:
        return [item for item in self.observations if item.endpoint == endpoint]


class TraceStore:
    def __init__(self):
        self.traces: list[Trace] = []

    def add(self, trace: Trace) -> None:
        self.traces.append(trace)

    def observations(self) -> list[Observation]:
        return [observation for trace in self.traces for observation in trace.observations]

    def write_jsonl(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8") as handle:
            for observation in self.observations():
                handle.write(json.dumps(asdict(observation), default=str) + "\n")
