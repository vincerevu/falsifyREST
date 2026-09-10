from core.models import Observation, Probe
from experiments.recipe_runner import run_recipes_with_adapter
from inference.hypothesis import PolicyHypothesis
from violation.counterfactual import CounterfactualContext


class RecipeAdapter:
    supports_fresh_control = False

    def __init__(self):
        self.calls = []

    def setup(self):
        pass

    def reset(self):
        pass

    def binding_context(self):
        return {"actor": {"owner": {"basket_id": "9"}}}

    def prepare_seed(self, probe):
        # Recipe seeds are already provisioned and must not be filtered by a
        # target adapter's captured-trace rebinding policy.
        return None

    def context_for(self, probe):
        return CounterfactualContext(owner_id="owner", alternate_actor="other")

    def protected_fields_for(self, probe):
        return set()

    def snapshot(self):
        return {}

    def execute(self, probe):
        self.calls.append(probe)
        body = {"data": {"id": 42}} if probe.method == "POST" else {}
        return Observation(200, body, {}, probe.actor, probe.method, probe.path)


def test_recipe_runner_provisions_binds_and_cleans_up_a_resource_without_target_logic():
    adapter = RecipeAdapter()
    recipes = {
        "item": {
            "setup": [{"request": {"actor": "owner", "method": "POST", "path": "/items", "body": {"basket": "${actor.owner.basket_id}"}, "save": {"resource_id": "$.data.id"}}}],
            "baseline": {"actor": "owner", "method": "PUT", "path": "/items/${resource.resource_id}", "body": {"quantity": 2}},
            "cleanup": [{"request": {"actor": "owner", "method": "DELETE", "path": "/items/${resource.resource_id}"}}],
        }
    }
    hypothesis = PolicyHypothesis("item-owner", "", "PUT /items/{id}", "item", family="ownership", target_operation="PUT /items/{id}")
    run = run_recipes_with_adapter([hypothesis], recipes, adapter, 1)
    assert run.provisioned == ["item"]
    assert [call.path for call in adapter.calls][:2] == ["/items", "/items/42"]
    assert adapter.calls[-1].path == "/items/42"
