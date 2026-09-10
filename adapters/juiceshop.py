"""Juice Shop authentication plumbing; no policy/search logic belongs here."""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import json
import re
from dataclasses import replace
from typing import Callable

from actors.actor import Actor
from cli.session import ActorConfig
from core.models import Observation, Probe
from execution.http_executor import HTTPExecutor
from violation.counterfactual import CounterfactualContext


@dataclass
class JuiceShopAdapter:
    base_url: str
    actor_configs: list[ActorConfig]
    protected_fields: set[str] = field(default_factory=set)
    resetter: Callable[[], None] = lambda: None
    executor: HTTPExecutor | None = None
    supports_fresh_control: bool = False
    _actors: dict[str, Actor] = field(default_factory=dict, init=False, repr=False)
    _last_snapshot: dict = field(default_factory=dict, init=False, repr=False)
    _baseline_owners: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _basket_ids: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def setup(self) -> None:
        self.executor = self.executor or HTTPExecutor(self.base_url)
        for config in self.actor_configs:
            self._ensure_and_login(config)

    def _ensure_and_login(self, config: ActorConfig) -> None:
        if not config.email or not config.password_value():
            raise ValueError(f"Juice Shop actor {config.name} requires email and password or password_env")
        try:
            self._login(config)
        except RuntimeError:
            self._register(config)
            self._login(config)

    def _register(self, config: ActorConfig) -> None:
        response = self._http().execute_as(Probe(
            f"register:{config.name}", "anonymous", "POST", "/api/Users", {
                "email": config.email, "password": config.password_value(), "passwordRepeat": config.password_value(),
                "securityQuestion": {"id": 1, "question": "Your eldest siblings middle name?"},
                "securityAnswer": "falsifyrest",
            },
        ), Actor("anonymous", "ANONYMOUS"))
        if not 200 <= response.status_code < 300 and response.status_code != 409:
            raise RuntimeError(f"Juice Shop registration failed for {config.name}: HTTP {response.status_code}")

    def _login(self, config: ActorConfig) -> None:
        response = self._http().execute_as(Probe(
            f"login:{config.name}", "anonymous", "POST", "/rest/user/login",
            {"email": config.email, "password": config.password_value()},
        ), Actor("anonymous", "ANONYMOUS"))
        authentication = response.response_body.get("authentication") if isinstance(response.response_body, dict) else None
        token = authentication.get("token") if isinstance(authentication, dict) else authentication
        if not 200 <= response.status_code < 300 or not token:
            raise RuntimeError(f"Juice Shop login failed for {config.name}: HTTP {response.status_code}")
        self._actors[config.name] = Actor(config.name, config.role, token=str(token))
        try:
            part = str(token).split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode("utf-8"))
            basket_id = payload.get("bid") or payload.get("basketId")
            if basket_id is not None:
                self._basket_ids[config.name] = str(basket_id)
        except (IndexError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            pass

    def _http(self) -> HTTPExecutor:
        if self.executor is None:
            raise RuntimeError("JuiceShopAdapter.setup() must run before execute()")
        return self.executor

    def context_for(self, baseline: Probe) -> CounterfactualContext:
        alternate = next((name for name in self._actors if name != baseline.actor), None)
        self._baseline_owners[baseline.path] = baseline.actor
        return CounterfactualContext(
            owner_id=baseline.actor,
            alternate_actor=alternate,
            actor_sessions={name: True for name in self._actors},
        )

    def prepare_seed(self, baseline: Probe) -> Probe | None:
        """Rebind captured basket reads to the authenticated owner's live basket."""
        basket_id = self._basket_ids.get(baseline.actor)
        if basket_id is None:
            return None
        if re.fullmatch(r"/rest/basket/[^/]+", baseline.path):
            return replace(baseline, path=f"/rest/basket/{basket_id}")
        if re.fullmatch(r"/api/BasketItems/[^/]+", baseline.path):
            return baseline
        return None

    def exploration_headers_for(self, actor_name: str) -> list[str]:
        """Keep actor attribution and JWT injection at the target boundary."""
        actor = self._actors.get(actor_name)
        if actor is None or not actor.token:
            raise ValueError(f"No authenticated Juice Shop actor named {actor_name}")
        return [f"Authorization: Bearer {actor.token}", f"X-FalsifyREST-Actor: {actor_name}"]

    def seed_exploration(self, proxy_url: str) -> list[Probe]:
        """Capture one owner-controlled basket read as a concrete live seed."""
        seeds: list[Probe] = []
        proxy = HTTPExecutor(proxy_url)
        for actor_name, basket_id in self._basket_ids.items():
            actor = self._actors[actor_name]
            tagged_actor = Actor(
                actor.id, actor.role,
                headers={**actor.headers, "X-FalsifyREST-Actor": actor_name,
                         "X-FalsifyREST-Resource-Type": "basket",
                         "X-FalsifyREST-Resource-Id": basket_id,
                         "X-FalsifyREST-Resource-Owner": actor_name},
                cookies=actor.cookies, token=actor.token,
            )
            probe = Probe(f"seed:basket:{actor_name}", actor_name, "GET", f"/rest/basket/{basket_id}")
            observation = proxy.execute_as(probe, tagged_actor)
            if 200 <= observation.status_code < 300:
                seeds.append(probe)
        return seeds

    def binding_context(self) -> dict:
        """Expose opaque resource identifiers, never credentials or JWTs."""
        return {"actor": {name: {"basket_id": basket_id} for name, basket_id in self._basket_ids.items()}}

    def execute(self, probe: Probe) -> Observation:
        actor = Actor("anonymous", "ANONYMOUS") if probe.actor == "anonymous" else self._actors.get(probe.actor)
        if actor is None:
            raise ValueError(f"No authenticated Juice Shop actor named {probe.actor}")
        observation = self._http().execute_as(probe, actor)
        owner = self._baseline_owners.get(probe.path)
        if owner and owner != probe.actor and 200 <= observation.status_code < 300 and isinstance(observation.response_body, dict):
            observation.features["protected_disclosure"] = True
        if isinstance(observation.response_body, dict):
            self._last_snapshot = dict(observation.response_body)
        return observation

    def snapshot(self) -> dict:
        return dict(self._last_snapshot)

    def protected_fields_for(self, baseline: Probe) -> set[str]:
        return set(self.protected_fields)

    def reset(self) -> None:
        self.resetter()
