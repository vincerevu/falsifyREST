"""Instantiate target adapters from the user-facing RunConfig."""
from cli.session import RunConfig

from .juiceshop import JuiceShopAdapter
from .target import TargetAdapter


def adapter_from_config(config: RunConfig) -> TargetAdapter:
    if config.target.type == "juiceshop":
        return JuiceShopAdapter(config.target.base_url, config.actors, protected_fields=set(config.live.protected_fields))
    raise ValueError(f"No live TargetAdapter registered for target type: {config.target.type}")
