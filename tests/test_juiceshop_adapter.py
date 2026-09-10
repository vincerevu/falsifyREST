from adapters.juiceshop import JuiceShopAdapter
from adapters.factory import adapter_from_config
from cli.session import ActorConfig, RunConfig
from core.models import Observation, Probe


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute_as(self, probe, actor):
        self.calls.append((probe, actor))
        if probe.path == "/rest/user/login":
            return Observation(200, {"authentication": {"token": f"token-{probe.body['email']}"}}, {}, actor.id, probe.method, probe.path)
        return Observation(200, {"items": []}, {}, actor.id, probe.method, probe.path)


def test_juiceshop_adapter_logs_in_once_and_selects_actor_token_per_probe():
    executor = FakeExecutor()
    adapter = JuiceShopAdapter("http://target", [
        ActorConfig("alice", email="alice@test", password="password"),
        ActorConfig("bob", email="bob@test", password="password"),
    ], executor=executor)
    adapter.setup()
    observation = adapter.execute(Probe("basket", "bob", "GET", "/rest/basket/1"))
    assert [probe.path for probe, _ in executor.calls].count("/rest/user/login") == 2
    assert executor.calls[-1][1].token == "token-bob@test"
    assert observation.actor == "bob"
    context = adapter.context_for(Probe("basket", "alice", "GET", "/rest/basket/1"))
    assert context.owner_id == "alice" and context.alternate_actor == "bob"


def test_session_loader_accepts_actor_mapping_and_password_environment_fields():
    config = RunConfig.from_dict({"target": {"type": "juiceshop", "base_url": "http://target"}, "actors": {
        "owner": {"email": "owner@test", "password_env": "OWNER_PASSWORD"},
    }})
    assert config.target.type == "juiceshop"
    assert config.target.openapi_source == "auto"
    assert config.actors[0].name == "owner"
    assert config.actors[0].password_env == "OWNER_PASSWORD"
    assert isinstance(adapter_from_config(config), JuiceShopAdapter)


def test_juiceshop_adapter_seeds_its_live_basket_through_capture_proxy(monkeypatch):
    import adapters.juiceshop as juiceshop_module
    executor = FakeExecutor()
    adapter = JuiceShopAdapter("http://target", [ActorConfig("owner", email="owner@test", password="password")], executor=executor)
    adapter.setup()
    adapter._basket_ids["owner"] = "7"
    monkeypatch.setattr(juiceshop_module, "HTTPExecutor", lambda _url: executor)
    seeds = adapter.seed_exploration("http://proxy")
    assert [(seed.actor, seed.path) for seed in seeds] == [("owner", "/rest/basket/7")]
    assert executor.calls[-1][1].headers["X-FalsifyREST-Resource-Owner"] == "owner"
