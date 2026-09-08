from core.models import ExecutionTrace, Probe, TraceStep
from inference.hypothesis import PolicyHypothesis
from search import CounterexampleSearchEngine
from search.operators import ActorSwap, OmitStep, Repeat
from violation.counterfactual import CounterfactualContext


def test_search_finds_actor_swap_witness_without_family_dispatch():
    hypothesis = PolicyHypothesis(
        "h", "owner", "POST /orders/1/refund", "order",
        applicable_operators={"actor_swap"}, relevant_dimensions={"actor"},
    )
    seed = ExecutionTrace.from_probe(Probe("refund", "owner", "POST", "/orders/1/refund"))
    engine = CounterexampleSearchEngine([ActorSwap(), Repeat()])
    result = engine.search(hypothesis, seed, 2, CounterfactualContext(alternate_actor="other"),
                           lambda node: node.trace.steps[-1].probe.actor == "other")
    assert result.counterexample is not None
    assert result.counterexample.transformations == ("actor_swap",)


def test_omit_step_keeps_target_action_in_a_workflow():
    trace = ExecutionTrace("checkout", [
        TraceStep(Probe("login", "a", "POST", "/login")),
        TraceStep(Probe("checkout", "a", "POST", "/checkout")),
    ])
    changed = OmitStep().apply(trace, CounterfactualContext())
    assert [step.probe.id for step in changed.steps] == ["checkout"]
