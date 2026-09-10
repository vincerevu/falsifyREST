# falsifyREST

falsifyREST is a standalone policy-guided REST security-testing prototype. EvoMaster is an external state/setup exploration provider; falsifyREST imports its traces, infers structured policy hypotheses, constructs minimal counterfactual workflows, and validates protected effects before reporting a counterexample.

## API-agnostic core boundary

The research method is target-agnostic. Code under `core/`, `inference/`, `search/`, `oracle/`, and `violation/` must not contain benchmark-specific endpoint names, roles, workflow states, or vulnerability rules.

Target-specific mechanics live behind `adapters.target.TargetAdapter`. An adapter may know how a concrete SUT authenticates actors, creates resources, reaches a state, resets the system, and observes protected fields. Those mechanics are experiment plumbing, not policy inference.

`experiments.target_runner.run_with_adapter()` is the shared active runner. It selects hypotheses by HTTP method plus OpenAPI path template, asks the adapter for a concrete `CounterfactualContext`, and delegates the experiment to the generic `ActivePolicyEngine`.

This distinction is intentional: the core is reusable across REST APIs, while zero-configuration execution is not claimed. OpenAPI alone does not reliably reveal credentials, ownership relations, state-setup procedures, reset semantics, or protected effects.

## Run

### Interactive CLI

Install the project with its CLI dependencies, then launch the configuration wizard:

```powershell
pip install -e .
falsifyrest
```

The wizard only collects a `RunConfig`; generic analysis/execution remains in the shared runner and target adapters own authentication, setup, snapshots, and reset behavior. Profiles are saved under `~/.falsifyrest/profiles`.

The same configuration can be used non-interactively for benchmarks or CI:

```powershell
falsifyrest run --config juiceshop.yaml --no-interactive
falsifyrest run --no-interactive --target http://localhost:3000 --openapi .\openapi.json --mode rule-only --budget 50
```

For existing captured traces, add `--trace .\trace.jsonl`; this invokes the generic trace → evidence → hypothesis analysis without assuming a target-specific live-execution adapter.

For Juice Shop, start from [juiceshop.example.yaml](configs/juiceshop.example.yaml). Set the two password environment variables instead of storing passwords in the profile. The `JuiceShopAdapter` creates missing benchmark users when permitted, logs each actor in once, caches its JWT privately, and attaches the appropriate token during request execution.

With Juice Shop running, the supplied profile starts a local capture proxy, performs one authenticated EvoMaster pass per configured actor, then imports that trace for inference and live validation:

When `recipe_synthesis.enabled` is true, active seeds are generated in batches from OpenAPI operations and successful trace shapes. Each proposed recipe is structurally checked against OpenAPI, executed against the target, and repaired with the configured LLM when provisioning fails. The local Juice Shop profile intentionally contains no fixed basket recipes; YAML resources remain an optional override/fallback.

```powershell
$env:FALSIFYREST_JUICESHOP_OWNER_PASSWORD = "..."
$env:FALSIFYREST_JUICESHOP_ATTACKER_PASSWORD = "..."
falsifyrest run --config .\configs\juiceshop.local.yaml --no-interactive --live
```

Live results are written to `output/live-results.json`. The overall budget is divided across selected captured seeds; the adapter never prints JWTs.

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

The toy scenario is an example target only. Its names and workflow must not be imported into the generic algorithm.

`schema/`, `actors/`, `execution/trace_store.py`, `resources/`, `evidence/`, `inference/`, `violation/`, `search/`, and `oracle/` provide the reusable modules. `adapters/EvoMasterProvider` launches EvoMaster in black-box mode and returns an `ExplorationResult`; when a proxy JSONL is supplied it includes normalized traces through `ProxyTraceImporter`. It intentionally does not parse generated EvoMaster source tests.

## Juice Shop handoff

`configs/juiceshop.example.json` points at the full 138-operation OpenAPI artifact already generated for the local Juice Shop instance. Supply only runtime credentials for the configured actors; do not commit them. With Docker Desktop running, the integration flow is: start the authorized local target, use `EvoMasterProvider` against the schema/base URL, capture normalized HTTP JSONL through a proxy, import it using `ProxyTraceImporter`, then use the same tracker → inference → counterexample → effect-oracle pipeline.

For full-spec trace analysis, copy the example to ignored `configs/juiceshop.local.json`, capture EvoMaster traffic as normalized JSONL, then run:

```powershell
python -m experiments.juiceshop_benchmark_runner --config configs/juiceshop.local.json --trace D:\Research\runs\juiceshop-proxy.jsonl
```

This reports OpenAPI/trace coverage and evidence-derived hypotheses across the whole specification. Live active execution requires explicit target authentication, setup, context, snapshot, reset, and protected-field behavior through a `TargetAdapter`; the algorithm does not guess these from an OpenAPI document or report findings from coverage alone.

## Scope

The repository includes toy targets for reproducible tests, but target-specific behavior is not part of the research method. No LLM is required and the oracle is deterministic. The package also includes a standard-library HTTP executor/session/reset layer. The EvoMaster adapter normalizes generated actions into `Probe` objects and does not modify EvoMaster.

## Rule-first, state-aware pipeline

`falsifyREST` is a rule-first, state-aware REST API security testing MVP. It builds semantic metadata, derives reproducible experiment templates, and uses deterministic effect/disclosure oracles for verdicts.

## Pipeline

1. Parse OpenAPI operations and produce static semantic metadata; these facts are not policies.
2. Import real HTTP traces and normalize them into an `EvidenceStore`.
3. Instantiate competing typed-predicate hypotheses only when runtime evidence supplies the required concrete facts.
4. Generate minimal counterfactual workflow transformations that change one relevant dimension at a time.
5. Select experiments under a request budget, execute them through a target adapter, and compare black-box observations/snapshots.
6. Validate the predicted policy against a deterministic effect/disclosure oracle and record a reproducible falsification witness.
7. Update support/contradiction from observed evidence and continue while budget remains.

`experiments.active_loop.ActivePolicyEngine` is the generic loop. Benchmark runners and target adapters are integration layers, not part of the core inference algorithm.

The generic loop requires an explicit `CounterfactualContext`: known owner/alternate identities when available, observed state, optional state-setup probes, optional observation probes, alternate resource bindings, and actor sessions. It will not silently pretend that copying a request changes identity or state. Replay executes an accepted baseline before repeating it; state-family experiments require a concrete alternative-state setup.

`EvaluationContext` is shared by counterfactual selection and evidence induction (`actor`, `resource`, `state`, `history`). The selector records an experiment fingerprint after execution, so an unchanged experiment cannot consume the remaining budget repeatedly.

`ERROR` evidence is excluded from belief updates. State-family predictions are recomputed from the snapshot taken after setup. Effect validation requires adapter- or hypothesis-supplied `protected_fields`, rather than assuming a particular domain field such as `status` or `balance`.

## Policy families

The generic registry currently includes ownership, authenticated-access authorization, state-transition, and replay families. A family is instantiated from typed runtime facts, not from a benchmark endpoint name. Adding a new family should mean adding a reusable predicate/evidence requirement and applicable generic trace transformations, never a target rule such as “if endpoint X then policy Y”.

## Semantic prior

The deterministic parser emits only static OpenAPI facts: method, path, parameter names, and resource/action hints. It does not itself assert a security policy. With LLM disabled, families use a uniform prior. With LLM enabled, semantic enrichment may influence initial family priors or labels only. Runtime evidence, counterfactual execution, and deterministic oracles remain the sole sources of policy support, contradiction, and vulnerability verdicts.

## Optional LLM semantic enrichment

LLM output is deliberately limited to semantic enrichment and optional priors. It cannot choose a final vulnerability verdict, replace runtime evidence, or replace the deterministic oracle. The default is disabled, which is the baseline for rule-only experiments.

```powershell
# Default: no LLM request
$env:FALSIFYREST_LLM_PROVIDER = "disabled"

# Local Ollama (optional)
$env:FALSIFYREST_LLM_PROVIDER = "ollama"
$env:FALSIFYREST_LLM_MODEL = "qwen2.5:7b"
$env:FALSIFYREST_LLM_BASE_URL = "http://localhost:11434/v1"
```

For another OpenAI-compatible server, set `FALSIFYREST_LLM_PROVIDER=openai`, `FALSIFYREST_LLM_BASE_URL`, `FALSIFYREST_LLM_MODEL`, and (when needed) `FALSIFYREST_LLM_API_KEY`. Never commit keys; the repository contains no provider credentials.
