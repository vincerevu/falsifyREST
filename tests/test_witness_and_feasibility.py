from dataclasses import replace

from core.models import ExecutionTrace, Probe, TraceStep
from inference.hypothesis import PolicyHypothesis
from oracle import FalsificationOracle
from search import CounterexampleSearchEngine, TraceFeasibilityChecker
from search import SeedSelector
from search.operators import ActorSwap, Reorder, ResourceSwap, Repeat
from violation.counterfactual import CounterfactualContext


def test_ownership_oracle_requires_a_relation_preserving_treatment():
    hypothesis = PolicyHypothesis("owner", "owner", "GET /orders/1", "order", family="ownership")
    seed = ExecutionTrace.from_probe(Probe("read", "alice", "GET", "/orders/1"))
    treatment = ActorSwap().apply(seed, CounterfactualContext(alternate_actor="bob"))
    from oracle.effect import EffectResult
    effect = EffectResult("EFFECTIVE_DISCLOSURE", True, "protected object returned")
    verdict = FalsificationOracle().evaluate(hypothesis, seed, treatment, effect, {
        "actor": {"id": "bob"}, "resource": {"owner_id": "alice"}, "state": {}, "history": {},
    })
    assert verdict.falsified
    assert verdict.classification == "SECURITY_RELEVANT_WITNESS"
    assert verdict.witness is not None
    assert verdict.witness.oracle_evidence.preservation_valid


def test_feasibility_rejects_unresolved_bindings_and_missing_sessions():
    trace = ExecutionTrace("pay", [TraceStep(Probe("pay", "bob", "POST", "/orders/1/pay"), consumes={"order_id"})])
    checker = TraceFeasibilityChecker()
    assert not checker.check(trace, CounterfactualContext()).valid
    trace.steps[0].consumes.clear()
    assert not checker.check(trace, CounterfactualContext(actor_sessions={"bob": False})).valid


def test_reorder_preserves_target_and_rejects_dependency_inversion():
    create = TraceStep(Probe("create", "a", "POST", "/orders"), produces={"order"})
    pay = TraceStep(Probe("pay", "a", "POST", "/orders/1/pay"), consumes={"order"})
    ship = TraceStep(Probe("ship", "a", "POST", "/orders/1/ship"))
    dependent = ExecutionTrace("flow", [create, pay, ship])
    assert not Reorder().applicable(PolicyHypothesis("h", "", "", ""), dependent, CounterfactualContext())
    independent = ExecutionTrace("flow", [TraceStep(Probe("login", "a", "POST", "/login")), pay, ship])
    assert Reorder().apply(independent, CounterfactualContext()).steps[-1].probe.id == "ship"


def test_seed_selector_uses_supporting_trace_ids_from_a_corpus():
    short = ExecutionTrace.from_probe(Probe("short", "a", "GET", "/orders/1"))
    supported = ExecutionTrace("supported", [
        TraceStep(Probe("setup", "a", "POST", "/orders")),
        TraceStep(Probe("target", "a", "GET", "/orders/1")),
    ])
    hypothesis = PolicyHypothesis("h", "", "GET /orders/1", "order", supporting_trace_ids=["supported"])
    assert SeedSelector().select(hypothesis, [short, supported]) == [supported]


def test_best_first_scores_children_before_executing_them():
    class CostlyMutation:
        name = "costly"
        affected_dimensions = frozenset({"actor"})

        def applicable(self, *_): return True

        def apply(self, trace, _):
            step = trace.steps[-1]
            return ExecutionTrace("costly", [replace(step, probe=replace(step.probe, id="costly", actor="costly", cost=10))])

    class CheapMutation(CostlyMutation):
        name = "cheap"

        def apply(self, trace, _):
            step = trace.steps[-1]
            return ExecutionTrace("cheap", [replace(step, probe=replace(step.probe, id="cheap", actor="cheap", cost=1))])

    hypothesis = PolicyHypothesis("h", "", "GET /x", "x", applicable_operators={"costly", "cheap"}, relevant_dimensions={"actor"})
    seen = []
    CounterexampleSearchEngine([CostlyMutation(), CheapMutation()]).search(
        hypothesis, ExecutionTrace.from_probe(Probe("seed", "a", "GET", "/x", cost=1)), 1, CounterfactualContext(),
        lambda node: seen.append(node.trace.id) or False,
    )
    assert seen == ["cheap"]


def test_mutations_preserve_dependency_metadata_and_stable_order_identity():
    seed = ExecutionTrace("read", [TraceStep(
        Probe("read", "alice", "GET", "/orders/1"), produces={"receipt"}, consumes={"order"}, session="alice-token", origin_step_id="read",
    )])
    context = CounterfactualContext(alternate_actor="bob", alternate_resource_path="/orders/2")
    for trace in (ActorSwap().apply(seed, context), ResourceSwap().apply(seed, context), Repeat().apply(seed, context)):
        assert trace.steps[-1].consumes == {"order"}
        assert trace.steps[-1].session == "alice-token"
        assert trace.steps[-1].stable_id == "read"
    hypothesis = PolicyHypothesis("owner", "", "GET /orders/1", "order", family="ownership")
    from oracle.effect import EffectResult
    verdict = FalsificationOracle().evaluate(hypothesis, seed, ActorSwap().apply(seed, context),
                                             EffectResult("EFFECTIVE_DISCLOSURE", True, "returned"),
                                             {"actor": {"id": "bob"}, "resource": {"owner_id": "alice"}, "state": {}, "history": {}})
    assert "order" not in verdict.witness.changed_dimensions


def test_authorization_witness_requires_negative_authentication_context():
    hypothesis = PolicyHypothesis("auth", "", "GET /orders/1", "order", family="authorization")
    seed = ExecutionTrace.from_probe(Probe("read", "alice", "GET", "/orders/1"))
    candidate = ActorSwap().apply(seed, CounterfactualContext(alternate_actor="bob"))
    from oracle.effect import EffectResult
    verdict = FalsificationOracle().evaluate(hypothesis, seed, candidate, EffectResult("EFFECTIVE_DISCLOSURE", True, "returned"), {
        "actor": {"id": "bob", "authenticated": True}, "resource": {}, "state": {}, "history": {},
    })
    assert not verdict.falsified


def test_oracle_labels_fresh_control_separately_from_historical_control():
    hypothesis = PolicyHypothesis("owner", "", "GET /orders/1", "order", family="ownership")
    seed = ExecutionTrace.from_probe(Probe("read", "alice", "GET", "/orders/1"))
    candidate = ActorSwap().apply(seed, CounterfactualContext(alternate_actor="bob"))
    from oracle.effect import EffectResult
    control = EffectResult("EFFECTIVE_DISCLOSURE", True, "owner returned object")
    verdict = FalsificationOracle().evaluate(hypothesis, seed, candidate, EffectResult("EFFECTIVE_DISCLOSURE", True, "foreign returned object"), {
        "actor": {"id": "bob"}, "resource": {"owner_id": "alice"}, "state": {}, "history": {}, "control_is_fresh": True,
    }, control)
    assert verdict.witness.oracle_evidence.control_provenance == "fresh"
