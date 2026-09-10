from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TargetConfig:
    base_url: str
    openapi: str = ""
    openapi_source: str = "auto"  # file, url, or auto
    type: str = "generic"


@dataclass
class ExplorationConfig:
    provider: str = "skip"  # evomaster, trace, skip
    trace_path: str | None = None
    evomaster_jar: str | None = None
    max_time: str = "1m"
    proxy_port: int = 3002


@dataclass
class LLMConfig:
    mode: str = "rule-only"  # rule-only, llm-prior, compare
    provider: str = "disabled"  # ollama, openai, disabled
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None


@dataclass
class ActorConfig:
    name: str
    auth_type: str = "bearer"
    credential_env: str | None = None
    email: str | None = None
    password: str | None = None
    password_env: str | None = None
    role: str = "USER"

    def password_value(self) -> str | None:
        from os import getenv
        return getenv(self.password_env) if self.password_env else self.password


@dataclass
class LiveConfig:
    enabled: bool = False
    max_seeds: int = 10
    protected_fields: list[str] = field(default_factory=list)

@dataclass
class RecipeSynthesisConfig:
    enabled: bool = False
    max_repairs: int = 1
    batch_size: int = 15
    request_timeout: int = 600
    request_retries: int = 1
    retry_backoff: float = 3.0
    batch_delay: float = 1.0


@dataclass
class RunConfig:
    target: TargetConfig
    exploration: ExplorationConfig = field(default_factory=ExplorationConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    actors: list[ActorConfig] = field(default_factory=list)
    live: LiveConfig = field(default_factory=LiveConfig)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    recipe_synthesis: RecipeSynthesisConfig = field(default_factory=RecipeSynthesisConfig)
    budget: int = 50
    output_dir: str = "output"
    profile_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunConfig":
        raw_actors = value.get("actors", [])
        if isinstance(raw_actors, dict):
            raw_actors = [{"name": name, **details} for name, details in raw_actors.items()]
        return cls(
            target=TargetConfig(**value["target"]),
            exploration=ExplorationConfig(**value.get("exploration", {})),
            llm=LLMConfig(**value.get("llm", {})),
            actors=[ActorConfig(**actor) for actor in raw_actors],
            live=LiveConfig(**value.get("live", {})),
            resources=dict(value.get("resources", {})),
            recipe_synthesis=RecipeSynthesisConfig(**value.get("recipe_synthesis", {})),
            budget=int(value.get("budget", 50)), output_dir=value.get("output_dir", "output"),
            profile_name=value.get("profile_name"),
        )


def load_config(path: str | Path) -> RunConfig:
    source = Path(path)
    with source.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    return RunConfig.from_dict(value)


def save_config(config: RunConfig, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False)
    return destination


def profiles_dir() -> Path:
    return Path.home() / ".falsifyrest" / "profiles"


def list_profiles() -> list[Path]:
    return sorted(profiles_dir().glob("*.yaml"))
