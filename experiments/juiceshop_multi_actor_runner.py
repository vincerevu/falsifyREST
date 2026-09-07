"""Authenticated three-actor Juice Shop benchmark runner.

This is deliberately target-specific glue.  It supplies real identities and one
known basket ownership relation to the otherwise target-agnostic benchmark core;
it does not add policy rules to inference.
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

from actors import Actor
from adapters.evomaster_provider import EvoMasterProvider
from core.models import Observation, Probe
from execution.http_executor import HTTPExecutor
from experiments.juiceshop_benchmark_runner import analyze, run_active, write_csv
from violation.counterfactual import CounterfactualContext


def _jwt_payload(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode("utf-8"))


def _success(observation, action: str) -> None:
    if not 200 <= observation.status_code < 300:
        raise RuntimeError(f"{action} failed: HTTP {observation.status_code}")


def register_user(base_url: str, actor_id: str) -> Actor:
    executor = HTTPExecutor(base_url)
    email, password = f"falsifyrest-{uuid.uuid4().hex[:12]}@juice-sh.op", "FalsifyREST123!"
    anonymous = Actor("anonymous", "ANONYMOUS")
    _success(executor.execute_as(Probe("register", "anonymous", "POST", "/api/Users", {
        "email": email, "password": password, "passwordRepeat": password,
        "securityQuestion": {"id": 1, "question": "Your eldest siblings middle name?"}, "securityAnswer": "falsifyrest",
    }), anonymous), f"register {actor_id}")
    response = executor.execute_as(Probe("login", "anonymous", "POST", "/rest/user/login", {"email": email, "password": password}), anonymous)
    _success(response, f"login {actor_id}")
    authentication = response.response_body.get("authentication") if isinstance(response.response_body, dict) else None
    token = authentication.get("token") if isinstance(authentication, dict) else authentication
    if not token:
        raise RuntimeError(f"login {actor_id} returned no JWT")
    basket_id = _jwt_payload(token).get("bid")
    if basket_id is None:
        raise RuntimeError(f"login {actor_id} JWT returned no basket id")
    actor = Actor(actor_id, "USER", token=token)
    actor.headers.update({"Authorization": f"Bearer {token}", "X-FalsifyREST-Actor": actor_id})
    actor.headers["X-FalsifyREST-Basket"] = str(basket_id)
    return actor


def login_admin(base_url: str, email: str, password: str) -> Actor:
    executor, anonymous = HTTPExecutor(base_url), Actor("anonymous", "ANONYMOUS")
    response = executor.execute_as(Probe("admin-login", "anonymous", "POST", "/rest/user/login", {"email": email, "password": password}), anonymous)
    _success(response, "admin login")
    authentication = response.response_body.get("authentication") if isinstance(response.response_body, dict) else None
    token = authentication.get("token") if isinstance(authentication, dict) else authentication
    if not token:
        raise RuntimeError("admin login returned no JWT")
    actor = Actor("admin", "ADMIN", token=token)
    actor.headers.update({"Authorization": f"Bearer {token}", "X-FalsifyREST-Actor": "admin"})
    return actor


def seed_basket_evidence(proxy_url: str, owner: Actor, foreign: Actor) -> None:
    """Record the same concrete basket under owner and foreign actors."""
    basket_id = owner.headers["X-FalsifyREST-Basket"]
    for actor, relation in ((owner, "owner"), (foreign, "foreign")):
        actor.headers.update({"X-FalsifyREST-Resource-Type": "basket", "X-FalsifyREST-Resource-Id": basket_id,
                              "X-FalsifyREST-Resource-Owner": owner.id, "X-FalsifyREST-Relation": relation})
        _success(HTTPExecutor(proxy_url).execute_as(Probe("basket-seed", actor.id, "GET", f"/rest/basket/{basket_id}"), actor),
                 f"basket seed as {actor.id}")


def basket_snapshot(executor: HTTPExecutor, actor: Actor, basket_id: str) -> dict:
    observation = executor.execute_as(Probe("basket-snapshot", actor.id, "GET", f"/rest/basket/{basket_id}"), actor)
    _success(observation, f"snapshot basket as {actor.id}")
    body = observation.response_body if isinstance(observation.response_body, dict) else {}
    products = body.get("Products") if isinstance(body.get("Products"), list) else []
    return {"item_count": len(products), "total": body.get("total"), "coupon": body.get("couponData")}


def seed_state_transition(trace_path: Path, executor: HTTPExecutor, actor: Actor, basket_id: str) -> dict | None:
    """Create one real quantity transition and persist its before/after state."""
    before = basket_snapshot(executor, actor, basket_id)
    created = executor.execute_as(Probe("state-seed-create", actor.id, "POST", "/api/BasketItems",
                                        {"ProductId": 1, "BasketId": int(basket_id), "quantity": 1}), actor)
    if not 200 <= created.status_code < 300 or not isinstance(created.response_body, dict):
        return None
    data = created.response_body.get("data") if isinstance(created.response_body.get("data"), dict) else {}
    item_id = created.response_body.get("id") or data.get("id")
    if item_id is None:
        return None
    update_path = f"/api/BasketItems/{item_id}"
    before_update = basket_snapshot(executor, actor, basket_id)
    updated = executor.execute_as(Probe("state-seed-update", actor.id, "PUT", update_path, {"quantity": 2}), actor)
    after = basket_snapshot(executor, actor, basket_id)
    if not 200 <= updated.status_code < 300:
        return None
    record = {"status_code": updated.status_code, "method": "PUT", "endpoint": update_path, "actor": actor.id,
              "request_body": {"quantity": 2}, "response_body": updated.response_body, "response_headers": updated.headers,
              "extracted_ids": {"resource_id": str(item_id)}, "features": {"resource_type": "basket_item"},
              "state_before": before_update, "state_after": after, "timestamp": updated.timestamp}
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return {"operation": f"PUT {update_path}", "item_id": str(item_id), "state_before": before_update, "state_after": after,
            "probe": {"id": "active-state", "actor": actor.id, "method": "PUT", "path": update_path, "body": {"quantity": 2}},
            "setup": {"id": "active-state-setup", "actor": actor.id, "method": "PUT", "path": update_path, "body": {"quantity": 1}}}


def _wait_for_proxy(url: str) -> None:
    for _ in range(30):
        try:
            urlopen(url + "/api-docs/", timeout=2)
            return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("capture proxy did not become ready")


def run(config_path: str | Path, trace_path: str | Path, output: str | Path, csv_path: str | Path,
        minutes_per_actor: str = "10m", explore: bool = True) -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    target = config["target"]["base_url"].rstrip("/")
    proxy = config.get("multi_actor", {}).get("proxy_url", "http://127.0.0.1:3002")
    proxy_port = int(proxy.rsplit(":", 1)[1])
    trace = Path(trace_path)
    trace.parent.mkdir(parents=True, exist_ok=True)
    if not explore and not trace.exists():
        raise FileNotFoundError(f"cannot reuse missing trace: {trace}")
    process = None
    if explore:
        trace.unlink(missing_ok=True)
        process = subprocess.Popen([sys.executable, "-m", "adapters.capture_proxy", "--upstream", target,
                                    "--trace", str(trace), "--port", str(proxy_port)])
    try:
        if explore:
            _wait_for_proxy(proxy)
        user_a, user_b = register_user(target, "user_a"), register_user(target, "user_b")
        if explore:
            seed_basket_evidence(proxy, user_a, user_b)
        admin_config = config.get("multi_actor", {}).get("admin", {"email": "admin@juice-sh.op", "password": "admin123"})
        actors = [user_a, user_b, login_admin(target, admin_config["email"], admin_config["password"])]
        evomaster = config["evomaster"]
        runs = []
        if explore:
            for actor in actors:
                headers = [f"Authorization: Bearer {actor.token}", f"X-FalsifyREST-Actor: {actor.id}"]
                result = EvoMasterProvider(evomaster["jar"], config["target"]["openapi"], proxy,
                                           Path(evomaster["output_folder"]) / actor.id, minutes_per_actor, headers).run()
                runs.append({"actor": actor.id, "returncode": result.returncode})
        state_seed = seed_state_transition(trace, HTTPExecutor(target), user_a, user_a.headers["X-FalsifyREST-Basket"])
        report, hypotheses, _ = analyze(config_path, trace)
        actor_map = {actor.id: actor for actor in actors}
        actor_map["anonymous"] = Actor("anonymous", "ANONYMOUS")
        executor = HTTPExecutor(target)
        basket_id = user_a.headers["X-FalsifyREST-Basket"]
        baseline = Probe("active-basket", user_a.id, "GET", f"/rest/basket/{basket_id}")

        def execute(probe: Probe) -> Observation:
            observation = executor.execute_as(probe, actor_map[probe.actor])
            if probe.path == baseline.path and probe.actor in {"user_b", "anonymous"} and observation.status_code < 300 and isinstance(observation.response_body, dict):
                observation.features["protected_disclosure"] = True
            return observation

        def snapshot() -> dict:
            current = executor.execute_as(baseline, user_a)
            body = current.response_body if isinstance(current.response_body, dict) else {}
            return {"Products": body.get("Products", []), "couponData": body.get("couponData"), "total": body.get("total")}

        seeds = [(baseline, CounterfactualContext(owner_id=user_a.id, alternate_actor=user_b.id))]
        if state_seed:
            state_probe = Probe(**state_seed["probe"])
            setup_probe = Probe(**state_seed["setup"])
            seeds.append((state_probe, CounterfactualContext(owner_id=user_a.id, alternate_actor=user_b.id,
                                                               state=state_seed["state_before"], state_setup_probes=[setup_probe])))
        active = run_active(hypotheses, seeds, execute, snapshot, budget_per_seed=4, protected_fields=set())
        active_outcomes = [outcome for item in active for outcome in item["outcomes"]]
        actor_counts = Counter(item.actor for sequence in __import__("adapters.proxy", fromlist=["ProxyTraceImporter"]).ProxyTraceImporter().load(trace)
                               for item in sequence.observations)
        payload = {"analysis": report.__dict__, "hypotheses": [item.__dict__ for item in hypotheses], "actors": dict(actor_counts), "runs": runs,
                   "state_seed": state_seed,
                   "active": active, "active_outcome_counts": dict(Counter(item["result"] for item in active_outcomes)),
                   "note": "Three authenticated static-header EvoMaster passes plus live active counterfactual execution on the verified basket seed. State hypotheses require a successful state-changing workflow with before/after snapshots."}
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        write_csv(csv_path, report, extra={"actors_observed": ";".join(sorted(actor_counts)), "authenticated_observations": sum(v for k, v in actor_counts.items() if k != "anonymous"),
                                           "evomaster_actor_passes": len(runs), "minutes_per_actor": minutes_per_actor,
                                           "active_counterfactuals": len(active_outcomes), "active_counterexamples": sum(item["result"] == "COUNTEREXAMPLE" for item in active_outcomes),
                                           "active_policy_holds": sum(item["result"] == "POLICY_HOLDS" for item in active_outcomes)})
        return payload
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible authenticated three-actor Juice Shop benchmark.")
    parser.add_argument("--config", default="configs/juiceshop.local.json")
    parser.add_argument("--trace", default="output/juiceshop-full-proxy-run2.jsonl")
    parser.add_argument("--output", default="output/juiceshop-benchmark-run2-analysis.json")
    parser.add_argument("--csv", default="output/juiceshop-benchmark-run2.csv")
    parser.add_argument("--minutes-per-actor", default="10m")
    parser.add_argument("--reuse-trace", action="store_true", help="Reuse an existing full trace and run active inference/oracle only.")
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.trace, args.output, args.csv, args.minutes_per_actor, not args.reuse_trace), indent=2, default=str))


if __name__ == "__main__":
    main()
