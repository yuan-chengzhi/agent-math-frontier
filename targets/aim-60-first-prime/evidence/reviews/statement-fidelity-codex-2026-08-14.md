# Statement-fidelity review: AIM Problem 60 launch target

Date checked: 2026-08-14

Verdict: **CONDITIONAL**. The exact candidate statement is mathematically coherent and safely claim-limited, but it is a strict, resource-bounded subproblem derived from AIM Problem 60, not an equivalent restatement. One catalog-level wording mismatch must be corrected before activation, and the domain convention for `a` must remain explicit.

## Materials checked

- The official AIM workshop [public problem list](https://aimath.org/pastworkshops/aint26problemlist.pdf), especially Problem 60. Freshly retrieved bytes had SHA-256 `4bf2321149bb0a7ad1eae4f6a767b23d7a2f7eceb73f49aee4832a4cff057a37`, matching `source-metadata.json`.
- [OEIS A122131](https://oeis.org/A122131), used only as a cross-check for the frozen `a=488669` sequence and the independently checkable congruence optimization.
- `target-card.json`, `candidate.schema.json`, the target README, the baseline source metadata and certificate, `data/problems.json`, and the semantic input/acceptance path of the checker.

## What the source asks

Problem 60 asks for `a < 10^20` that makes the least positive integer `x` for which `x^12+a` is prime as large as possible. It gives the example `a=488669`, composite for `1 <= x <= 616979` and prime at `x=616980`, and states that no `a < 10^6` gives a larger first prime.

The printed problem does not explicitly say that `a` is an integer or that `a > 0`, although integrality is implicit in asking whether `x^12+a` is prime and positivity is strongly suggested by the optimization and the `a < 10^6` comparison. Read literally with arbitrary negative integers and no lower bound, the statement is not the finite search problem the surrounding example plainly intends. The campaign therefore needs to present `1 <= a < 10^20` as an explicit interpretation/launch restriction, not as words quoted from the source.

## What the frozen target proves

The target accepts one positive integer `a < 10^20` and one

```text
616981 <= x0 <= 10000000
```

such that all values at positive `x < x0` are composite and the value at `x0` is prime. Because `a` is positive, every predecessor value is greater than 1, so "not prime" and "composite" are equivalent here. Complete coverage of `x=1,...,x0-1` and a proof of primality at `x0` therefore establish exactly the claimed first-prime index.

This gives a certified finite instance strictly later than the frozen public example. It does **not** maximize over all `a < 10^20`, prove a global optimum, prove a current world record, or verify the source's separate no-better-choice claim for every `a < 10^6`. The upper bound `x0 <= 10^7` is a campaign resource cap absent from the AIM statement. It is acceptable only because acceptance remains a valid instance and failure within the cap is not reported as a negative mathematical result.

The target card and README state these limitations clearly, and `claim_scope = FINITE_INSTANCE` is appropriate. The certificate additions (congruence covers, exact residual factors, and ECPP) strengthen evidence without changing the finite mathematical claim.

## Blocking catalog mismatch and required fixes

`data/problems.json` currently describes the launch as accepting a "public-record improvement" and "freezing the current record" (`刷新公开记录` / `冻结当前纪录`), and its risk text says that the "current record" may change. That is stronger than both the primary source evidence and the target card, which deliberately freezes only one public example and disclaims current-record status. Because the target card is hash-bound to that catalog entry, this is not harmless prose drift.

Before activation:

1. Replace the catalog's current-record language with "strictly beats the frozen public example `a=488669, x0=616980`; no current-record or optimality claim." Recompute the bound problem-card hash and dependent target metadata through the normal contract workflow.
2. Expose the relationship as `STRICT_DERIVED_SUBPROBLEM` (or equally unambiguous prose) wherever agents select the target: positive integer `a`, finite `x0 <= 10^7`, and finite-instance success only.
3. Either obtain source-author/domain-expert confirmation that AIM Problem 60 intends positive integers `a`, or retain the positive-domain choice explicitly as a campaign interpretation. Do not silently attribute `a > 0` or the `10^7` cap to the PDF.
4. Preserve the rule that exceeding the frozen example is not called "solving AIM #60," "optimal," or "current record" without separate evidence.

The targeted tests accepted the exact frozen baseline only in baseline mode, rejected it as a production improvement, and confirmed complete predecessor coverage. These checks support the finite-instance semantics but are not a verifier red-team review.
