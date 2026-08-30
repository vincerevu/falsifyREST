# Juice Shop policy-guided pipeline — 2026-08-30

Target: authorized local custom Juice Shop container at `http://localhost:3001`.

## Pipeline result

1. **OpenAPI discovery / EvoMaster black box**
   - Input: the generated Juice Shop OpenAPI document with 138 operations.
   - EvoMaster 6.1.1 bounded run: 70 seconds, 305 generated tests, 5,468 evaluated HTTP calls.
   - EvoMaster observed 138 operations and emitted 35 fault records across 21 operations. These are fuzzer/schema signals (for example, HTTP 500 or schema mismatch), not validated business-logic findings.
   - Artifacts: `evomaster-juiceshop-20260830-bounded/`.

2. **SecBelief policy inference and falsification**
   - Seed trace: user A registers/logs in and reads its own basket.
   - Inferred policy hypothesis: `actor == resource.owner` for `GET /rest/basket/{id}`.
   - Counterfactual: user B sends `GET /rest/basket/8`, where basket 8 belongs to user A.
   - Expected: `DENY`.
   - Observed: HTTP 200 and basket resource data.
   - Effect oracle: `EFFECTIVE_DISCLOSURE`.
   - Verdict: `COUNTEREXAMPLE`.

## Comparison with prior authorization-tool reports

| Tool/report | Reported `GET /rest/basket/{id}`? | Result |
|---|---:|---|
| AuthProbe Juice Shop run (2026-08-27) | No | It reported 7 missing-auth collection endpoints. |
| BACScan Juice Shop API run (2026-08-27) | No | It reported 10 horizontal/vertical cases on other endpoints. |
| SecBelief policy run (2026-08-30) | Yes | Validated cross-user basket disclosure with an authenticated A/B counterexample. |

The comparison is only against the saved runs and their configurations. It does not claim that AuthProbe or BACScan can never find this endpoint under a different configuration.

## Evidence

- `juiceshop-policy-result.json`: structured hypothesis, request, HTTP result, and effect verdict.
- `evomaster-juiceshop-20260830-bounded/report.json`: EvoMaster run report and generated suite metadata.
