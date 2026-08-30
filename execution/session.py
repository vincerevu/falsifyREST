from dataclasses import dataclass, field


@dataclass
class Session:
    actor: str
    headers: dict[str, str] = field(default_factory=dict)

    def with_json(self) -> dict[str, str]:
        return {"Accept": "application/json", "Content-Type": "application/json", **self.headers}
