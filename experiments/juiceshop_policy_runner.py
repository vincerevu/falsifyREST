"""Authorized local Juice Shop policy-guided cross-user basket test."""
import base64
import json
import uuid
from dataclasses import asdict
from pathlib import Path

from actors import Actor, ActorManager
from core.models import Probe
from execution.http_executor import HTTPExecutor
from execution.trace_store import Trace, TraceStore
from inference import infer_ownership_policies, rank
from oracle import classify_disclosure, compare
from reports import write_finding
from resources import ResourceTracker
from violation import violate_ownership


BASE_URL = "http://localhost:3001"


def _jwt_payload(token: str) -> dict:
    encoded = token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))


def _require_success(observation, action: str) -> None:
    if not 200 <= observation.status_code < 300:
        raise RuntimeError(f"{action} failed with HTTP {observation.status_code}: {observation.response_body}")


def _register_and_login(executor: HTTPExecutor, actor_id: str) -> Actor:
    actor = Actor(actor_id, "USER")
    email = f"secbelief-{uuid.uuid4().hex[:12]}@juice-sh.op"
    password = "SecBelief123!"
    registration = Probe("register", "anonymous", "POST", "/api/Users", {
        "email": email, "password": password, "passwordRepeat": password,
        "securityQuestion": {"id": 1, "question": "Your eldest siblings middle name?"}, "securityAnswer": "secbelief",
    })
    _require_success(executor.execute_as(registration, Actor("anonymous", "ANONYMOUS")), f"register {actor_id}")
    login = Probe("login", "anonymous", "POST", "/rest/user/login", {"email": email, "password": password})
    response = executor.execute_as(login, Actor("anonymous", "ANONYMOUS"))
    _require_success(response, f"login {actor_id}")
    if not isinstance(response.response_body, dict) or not response.response_body.get("authentication"):
        raise RuntimeError("login response contained no authentication token")
    authentication = response.response_body["authentication"]
    payload = None
    if isinstance(authentication, dict):
        actor.token = authentication.get("token") or authentication.get("jwt")
        payload = authentication.get("payload") or authentication
    else:
        actor.token = authentication
    if not actor.token:
        raise RuntimeError("login response authentication object contained no token")
    actor.headers["Authorization"] = f"Bearer {actor.token}"
    actor.headers["X-SecBelief-Actor"] = actor_id
    actor.headers["X-SecBelief-Email"] = email
    payload = payload or _jwt_payload(actor.token)
    basket_id = payload.get("bid") or payload.get("basketId")
    if basket_id is None:
        basket_id = _jwt_payload(actor.token).get("bid")
    if basket_id is None:
        raise RuntimeError("login token contained no basket id")
    actor.headers["X-SecBelief-Basket"] = str(basket_id)
    return actor


def run(base_url: str = BASE_URL) -> dict:
    executor = HTTPExecutor(base_url)
    actor_a = _register_and_login(executor, "user_a")
    actor_b = _register_and_login(executor, "user_b")
    actors = ActorManager([actor_a, actor_b])
    basket_id = actor_a.headers["X-SecBelief-Basket"]
    trace, tracker = Trace(), ResourceTracker()

    owner_probe = Probe("read_basket", actor_a.id, "GET", f"/rest/basket/{basket_id}")
    owner_observation = executor.execute_as(owner_probe, actor_a)
    _require_success(owner_observation, "owner reads own basket")
    owner_observation.extracted_ids["resource_id"] = basket_id
    owner_observation.features.update({"resource_type": "basket", "owner": actor_a.id})
    trace.append(owner_observation)
    tracker.observe(owner_observation)
    store = TraceStore()
    store.add(trace)
    hypotheses = rank(infer_ownership_policies(store, tracker))
    if not hypotheses:
        raise RuntimeError("no ownership policy inferred from seed trace")
    hypothesis = hypotheses[0]
    resource = tracker.get("basket", basket_id)
    counterexample = violate_ownership(hypothesis, owner_probe, resource, actors)
    observed = executor.execute_as(counterexample.probe, actor_b)
    effect = classify_disclosure(observed, basket_id)
    result = compare(counterexample.expected, effect)
    return {
        "target": base_url, "workflow": "basket ownership", "hypothesis": asdict(hypothesis),
        "counterexample": asdict(counterexample), "expected": counterexample.expected,
        "observed_status": observed.status_code, "effect": asdict(effect), "result": result,
        "baseline_comparison": {
            "authprobe_reported_endpoint": False,
            "bacscan_reported_endpoint": False,
            "note": "Comparison is against the saved 2026-08-27 reports, not a claim about all possible configurations of either tool.",
        },
    }


if __name__ == "__main__":
    finding = run()
    output = Path(__file__).resolve().parents[1] / "output" / "juiceshop-policy-result.json"
    write_finding(output, finding)
    print(json.dumps(finding, indent=2))
