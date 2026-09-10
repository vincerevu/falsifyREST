from adapters.target import CallbackTargetAdapter
from core.models import Observation, Probe
from experiments.target_runner import run_with_adapter
from inference.hypothesis import PolicyHypothesis
from violation.counterfactual import CounterfactualContext


def test_generic_target_runner_owns_active_pipeline_and_adapter_owns_mechanics():
    resets, state = [], {"status": "PENDING"}

    def execute(probe):
        state["status"] = "SETTLED"
        return Observation(200, {}, {}, probe.actor, probe.method, probe.path,
                           features={"operation_id": "POST /claims/{claimId}/settle"})

    adapter = CallbackTargetAdapter(
        context_resolver=lambda _: CounterfactualContext(owner_id="owner", alternate_actor="other"),
        executor=execute,
        snapshotter=lambda: dict(state),
        protected_field_resolver=lambda _: {"status"},
        resetter=lambda: resets.append("reset"),
    )
    hypothesis = PolicyHypothesis(
        "owner", "", "POST /claims/{claimId}/settle", "claim", family="ownership",
        target_operation="POST /claims/{claimId}/settle", applicable_operators={"actor_swap"},
    )
    results = run_with_adapter([hypothesis], [Probe("settle", "owner", "POST", "/claims/12/settle")], adapter, 1)
    assert resets == ["reset"]
    assert results and results[0]["outcomes"]
