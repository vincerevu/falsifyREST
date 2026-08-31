# falsifyREST

falsifyREST is a standalone policy-guided REST security-testing prototype. EvoMaster is an external state/setup exploration provider; falsifyREST imports its traces, infers structured ownership policies, constructs a minimal counterfactual request, and validates a protected state effect before reporting a counterexample.

## Run

```powershell
cd D:\Research\falsifyREST
python -m experiments.runner --runs 100 --budget 5 --seed 7
```

The runner compares three strategies under the same toy workflow, candidates, request budget, and seeded randomness:

- `facts_only`: one state estimate and heuristic action order;
- `belief_heuristic`: competing hypotheses but random selection;
- `secbelief`: belief plus prediction-diversity selection.

Results are written to `output/summary.json`; every request and belief update is written as JSONL under `output/traces/`.

## Policy-guided flow

```powershell
python -m experiments.policy_runner
```

This end-to-end toy run creates and pays an order as `user_a`, infers `actor == resource.owner` for refund from a successful trace, then has `user_b` refund the same paid order. The target intentionally permits this; the effect oracle verifies `PAID -> REFUNDED` and records `COUNTEREXAMPLE` in `output/policy-toy-result.json`.

`schema/`, `actors/`, `execution/trace_store.py`, `resources/`, `inference/`, `violation/`, and `oracle/` provide the MVP modules. `adapters/EvoMasterProvider` launches EvoMaster in black-box mode; `ProxyTraceImporter` reads normalized JSONL captured between EvoMaster and a target. It intentionally does not parse generated EvoMaster source tests.

## Juice Shop handoff

`configs/juiceshop.example.json` points at the full 138-operation OpenAPI artifact already generated for the local Juice Shop instance. Supply only runtime credentials for `user_a`, `user_b`, and `admin`; do not commit them. With Docker Desktop running, the next integration run is: start the authorized local target, use `EvoMasterProvider` against the schema/base URL, capture normalized HTTP JSONL through a proxy, import it using `ProxyTraceImporter`, then use the same tracker → inference → counterexample → effect-oracle pipeline shown by `policy_runner`.

## Scope

The toy target models `DRAFT -> SUBMITTED -> APPROVED`. The intentional vulnerability is that a manager can approve a draft order. No LLM is used and the oracle is deterministic. The package also includes a standard-library HTTP executor/session/reset layer. The EvoMaster adapter is offline-only: it normalizes generated actions into `Probe` objects and does not modify EvoMaster.

## Rule-first, state-aware pipeline

`falsifyREST` is a rule-first, state-aware REST API security testing MVP. It builds semantic metadata, derives reproducible experiment templates, and uses deterministic effect/disclosure oracles for verdicts.

## Pipeline

1. Parse OpenAPI operations.
2. Infer resources, actions, and candidate security concepts with deterministic rules.
3. Generate ownership, state-transition, and replay hypotheses.
4. Plan actor-separated experiment sequences and prioritize them transparently.
5. Execute through the configured runner, then let effect/disclosure oracles decide `COUNTEREXAMPLE`, `POLICY_HOLDS`, or `INCONCLUSIVE`.
6. Feed only those oracle results back into scheduling confidence.

## Optional LLM semantic enrichment

LLM output is deliberately limited to resource/action labels and candidate invariants. It cannot choose requests, infer an authorization verdict, or mark a vulnerability. The default is disabled, which is the baseline for rule-only experiments.

```powershell
# Default: no LLM request
$env:FALSIFYREST_LLM_PROVIDER = "disabled"

# Local Ollama (optional)
$env:FALSIFYREST_LLM_PROVIDER = "ollama"
$env:FALSIFYREST_LLM_MODEL = "qwen2.5:7b"
$env:FALSIFYREST_LLM_BASE_URL = "http://localhost:11434/v1"
```

For another OpenAI-compatible server, set `FALSIFYREST_LLM_PROVIDER=openai`, `FALSIFYREST_LLM_BASE_URL`, `FALSIFYREST_LLM_MODEL`, and (when needed) `FALSIFYREST_LLM_API_KEY`. Never commit keys; the repository contains no provider credentials.
