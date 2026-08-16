# Independent verifier red-team: stretched Littlewood--Richardson target

Date: 2026-08-14  
Reviewer: `codex-verifier-red-team-2026-08-14`  
Verifier: `amf.stretched-lr.exact.v1`  
Verdict: **PASS**

This report audits the exact implementation. It is not a receipt, an open-status
review, or evidence that a bounded negative-coefficient example has been found.

## Boundary audited

The frozen convention is
`P(t) = c^(t*lambda)_(t*mu,t*nu)`, with `lambda` outer, `mu` the inner shape,
and `nu` the content partition. All three partitions are nonempty, canonical,
have length at most seven and sum at most 30, and satisfy
`|lambda| = |mu| + |nu|`. A candidate supplies the complete reduced rational
monomial-basis polynomial and all exact values at `t=1,...,29`; at least one
coefficient must be negative.

The audited manifest SHA-256 is
`bd000a80ceb4f9b056bd27a5998b5cb7bec3b3b22d920426bf78509edd04d419`.

## Mathematical attacks

- Implemented a third, deliberately simple cell-by-cell LR-tableau enumerator.
  It fills the reverse row word directly, tests row weak increase, column strict
  increase, exact content, and every lattice-word prefix. On all 4,993 partition
  triples with outer size two through eight, it agreed with both production
  cores.
- Rechecked the role order on
  `c^(3,2,1)_((2,1),(2,1)) = 2` and on a non-skew role permutation. The outer,
  inner, and content roles were not silently swapped.
- Constructed the alias polynomial
  `t + 1 + product(t-i, i=1..29)`. It agrees with `t+1` at every declared sample
  and has negative coefficients, but has degree 29. Both cores reject it before
  oracle work because it violates the frozen degree/representation envelope.
  This directly attacks the most obvious 29-point interpolation exploit.
- Attacked unreduced rationals, zero denominators, trailing zero coefficients,
  negative sample values, the size equation, duplicate keys, floating JSON
  numbers, and mismatched declared values. They fail closed.

## Process, output, and source attacks

- Operation ceilings in both cores return infrastructure status. Forged checker
  exit 2 results remain dispatcher infrastructure failures.
- The dispatcher rejected malformed accepted facts, invalid digest grammar,
  exit-code/result inconsistency, disagreement, and malformed output.
- Copied-source byte drift and symlink replacement were rejected by the
  content-bound manifest.

The dedicated red-team suite contains 9 test methods covering 14 frozen corpus
classes and passed 9/9. The repository suite at audit completion passed 115/115.
No verifier source change was required.

## Independence assessment

The primary core directly counts LR tableaux and recovers the polynomial with
Newton differences. The secondary expands Jacobi--Trudi, counts signed Pieri
chains, and solves an exact Vandermonde system. Neither imports the other's
coefficient or interpolation implementation, and the dispatcher runs them in
separate processes. The 4,993-case third enumerator materially reduces the risk
of a shared small-case semantic error.

## Residual limits and claim ceiling

- Soundness of using 29 samples depends on the frozen source premise that the
  degree is at most `binomial(length(lambda)+1,2) <= 28`. This red team tested
  enforcement and interpolation, but source fidelity belongs to the separate
  statement review.
- No real negative-coefficient candidate was available, so production
  acceptance is exercised only through an explicitly patched synthetic oracle
  in the pre-existing suite. That seam is control-flow coverage, not
  mathematical evidence.
- Both exact algorithms can exceed their operation or wall-time envelopes on a
  hard candidate. Such an event is correctly inconclusive; it is not a proof
  that the candidate fails.
- Agreement does not establish novelty, current open status, or significance.
  Source checkout immutability remains a host responsibility after manifest
  validation.

Within the frozen degree premise and resource envelope, no false accept or
checker-disagreement exploit was found.

## Final-card recheck

Date: 2026-08-14  
Final target-card SHA-256: `1ab87748125aa10d24229cadc47c8d04a99add70aeb42465b8be8232b458aad8`  
Current verifier-manifest SHA-256: `bd000a80ceb4f9b056bd27a5998b5cb7bec3b3b22d920426bf78509edd04d419`  
Verdict: **PASS**

The final card preserves the audited convention, partition length and sum
bounds, size equation, exact 29-value certificate, complete reduced rational
polynomial, and negative-coefficient acceptance condition. The newly recorded
length-at-most-four positivity theorem changes route selection and the meaning
of partial progress only. It does not add a new mathematical hypothesis to a
counterexample or authorize the verifier to dismiss an exact contradictory
witness; such a witness would instead require heightened novelty review. The
route-baseline edit therefore creates no verifier claim gap, and the manifest
is byte-identical to the one red-teamed above.
