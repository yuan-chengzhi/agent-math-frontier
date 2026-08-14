# Independent verifier red-team: AIM Problem 60 finite target

Date: 2026-08-14  
Reviewer: `codex-verifier-red-team-2026-08-14`  
Verifier: `amf.aim60.certificate.v1`  
Verdict: **PASS AFTER REMEDIATION**

This is a verifier assessment. It is not a receipt, a claim that the frozen
example is a world record, or evidence of a new `a` with a later first prime.

## Boundary audited

For a positive `a < 10^20` and `616981 <= x0 <= 10000000`, every positive
`x < x0` must have an exact nontrivial compositeness witness. Congruence rules
may compress witnesses but are recomputed by the verifier; all uncovered
indices must appear in canonical order with proper factors. The final value
`x0^12+a` must have a checked Atkin--Morain ECPP chain ending in a deterministic
64-bit prime test.

The remediated manifest SHA-256 is
`4c6c63d7c63e7e96bd1b3e7dfc691c01ae130dbfa9b2db7583fccdf287d4e849`.

## Finding and remediation

### AIM-RT-01: verifier-resource exhaustion was encoded as rejection

Severity: medium for research-ledger correctness; no false-accept path.

`MemoryError`/`OverflowError` and the congruence-cover operation ceiling were
previously returned as `accepted=false` with exit 1. The PMW host interprets
that combination as mathematical rejection even though the apparatus did not
finish. The checker now has an explicit apparatus exception, returns status
alongside in-process results, and emits exit 2 for resource failures and
`COVER_OPERATION_LIMIT`. Compatibility wrappers preserve existing callers.
The source manifest and registry bindings were updated. Both direct exception
tests and a subprocess CLI test confirm exit 2 with one valid JSON result and
no stderr.

## Coverage and factor attacks

- Tested a divisor exactly equal to `x^12+a`. The rule does not mark that index
  covered; it begins only where the divisor is strictly smaller and therefore a
  genuine compositeness witness.
- Tested residue zero. Coverage starts at the first positive multiple of the
  divisor and never introduces `x=0` into the positive-domain claim.
- Independently reconstructed the covered/uncovered set for the frozen rules on
  the first 999 positive indices, including overlaps. No uncovered index can be
  omitted by double counting.
- Factors 1 and `x^12+a` itself are rejected; a proper exact factor is accepted.
  Canonical ordering, decimal grammar, Boolean indices, leading zeros, `+`
  signs, and negative zero were attacked and rejected.

## ECPP attacks and reasoning

The audit followed the actual elliptic criterion rather than trusting a status
flag. For every recursive step the checker requires an odd modulus above
`2^64`, a Hasse-bounded trace, order `s*q`, the exact lower bound on prime `q`,
chain equality, a unit discriminant, canonical point coordinates, `sP != O`,
and `sqP = O`. Affine additions reject every nonunit denominator. The terminal
`q < 2^64` is checked with the complete deterministic seven-base witness set.

Mutated chain links, too-small `q`, nonunit elliptic denominators, singular or
noncanonical points, and several known strong pseudoprimes were rejected. Tiny
prime-field scalar multiplication was also cross-checked against repeated
addition by the pre-existing suite.

## Test evidence

The dedicated red-team suite contains 11 test methods covering 15 frozen corpus
classes and passed 11/11. The repository suite after remediation passed
115/115. Static verifier-source byte drift and symlink replacement were rejected
by the manifest contract.

## Residual limits and claim ceiling

- This verifier has one ECPP implementation, not two independently coded ECPP
  engines. Its soundness rests on the audited elliptic primality criterion and
  Python exact-integer semantics; future format revisions should be reviewed
  anew.
- The accepted frozen baseline uses a baseline-only schema and does not satisfy
  the production improvement threshold. No production-positive target artifact
  was available.
- The ten-million index cap and all operation limits are target/resource
  boundaries. Exhausting them is inconclusive, and the remediation now records
  that correctly.
- Acceptance proves only the one finite first-prime instance under the frozen
  bound. It does not prove a world record, global optimality over `a`, novelty,
  or the broader AIM problem.
- The host must keep the content-pinned verifier checkout read-only between
  source validation and execution.

After remediation, no route to false acceptance was found.
