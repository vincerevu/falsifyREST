from core.models import ExecutionTrace, Probe, TraceStep
from inference.hypothesis import PolicyHypothesis
from oracle import FalsificationOracle
from search import TraceFeasibilityChecker
from search import SeedSelector
from search.operators import ActorSwap, Reorder
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
