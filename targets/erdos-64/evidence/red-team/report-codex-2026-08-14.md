# Independent verifier red-team: Erdős--Gyárfás counterexample checker

Date: 2026-08-14  
Reviewer: `codex-verifier-red-team-2026-08-14`  
Verifier: `amf.erdos64.counterexample.v1`  
Verdict: **PASS**

This report audits bounded graph-candidate acceptance. It is not a red-team
receipt, a novelty review, or evidence that a counterexample exists.

## Boundary audited

The checker accepts only a finite simple graph on `4 <= n <= 64` with minimum
degree at least three and no simple cycle of length `4`, `8`, `16`, `32`, or
`64` when that length is at most `n`. Connectivity is intentionally not a
hypothesis. Finishing every relevant search can accept; reaching the fixed step
ceiling must be an apparatus error.

The audited manifest SHA-256 is
`f342da701e876b882ebf2a25599a63243f01921102a384e84f6bb4ef9f6d66be`.

## Search-completeness attacks

- Exhausted all 32,768 labelled simple graphs on six vertices. Fixed-length C4
  detection agreed in every case with the independent characterization that a
  C4 exists exactly when some vertex pair has at least two common neighbors.
- On 80 deterministic random graphs of orders four through ten, made 120
  separate C4/C8 comparisons against an unpruned oriented simple-path search.
  All comparisons agreed.
- Checked cycles with chords to ensure “simple cycle” was not accidentally
  strengthened to “induced cycle.”
- Validated returned witnesses edge by edge. The least-vertex and
  `first < last` symmetry reductions retain exactly one of the two undirected
  orientations without dropping the cycle.
- Directly detected an exact 64-cycle and confirmed the relevant length list is
  `[4,8,16,32,64]` at the upper boundary.

## Statement and parser attacks

- Two disjoint 5-cycles are accepted at an explicit degree-two test seam after
  exhausting C4 and C8, while production rejects them for minimum degree. This
  demonstrates both that connectivity is not silently required and that the
  production degree threshold remains exact.
- Boolean endpoints, reversed edges, duplicate edges, duplicate JSON keys,
  out-of-range endpoints, loops, extra fields, and noninteger JSON fail closed.
- The deterministic step ceiling raises `SEARCH_STEP_LIMIT`; both direct and
  subprocess tests confirm exit 2, not mathematical rejection. Injected memory
  failure is also infrastructure status.
- Copied-source byte drift and symlink replacement fail manifest validation.

The dedicated red-team suite contains 11 test methods covering 14 frozen corpus
classes and passed 11/11. The repository suite at audit completion passed
115/115. No verifier source change was required.

## Completeness reasoning

For any undirected simple cycle, choose its least vertex as `start`. Every other
cycle vertex is strictly greater, so the search's `neighbor > start` restriction
does not remove it. The cycle has two orientations; exactly one orders the two
neighbors of `start` as `first < last`. The DFS otherwise enumerates unused
neighbors until the exact length and then checks the closing edge. Therefore a
completed search is exhaustive for that length. The step budget may interrupt
this argument only by returning apparatus failure, never acceptance.

## Residual limits and claim ceiling

- Exact fixed-length cycle absence is exponential. Many validly encoded graphs
  can hit the 20-million-step ceiling; this is intentional incompleteness and
  must not be reported as rejection or evidence for the conjecture.
- Exhaustive third-reference testing covered C4 through order six and random
  C4/C8 cases. Larger lengths received constructive boundary tests plus the
  symmetry/completeness argument, not exhaustive graph enumeration.
- No production-positive graph was available. Existing acceptance coverage at
  relaxed seams is control-flow evidence only.
- Acceptance of one graph would refute the frozen unrestricted statement, but
  current open status, novelty, source fidelity, and public resolution require
  their separate reviews.
- Runtime source immutability after manifest validation is a host sandbox
  responsibility.

No false accept, omitted power-of-two length, or resource-status confusion was
found.

## Final-card recheck

Date: 2026-08-14  
Final target-card SHA-256: `106f5e6d4ad516a7eee5e38e43244769dc5254ce10d357505c90c853dc53fbcd`  
Current verifier-manifest SHA-256: `f342da701e876b882ebf2a25599a63243f01921102a384e84f6bb4ef9f6d66be`  
Verdict: **PASS**

The final card keeps the audited full-counterexample direction: one canonical
simple graph on 4 through 64 vertices, minimum degree at least three, no added
connectivity requirement, and exhaustive absence of every relevant length in
`4, 8, 16, 32, 64` before acceptance. `SEARCH_STEP_LIMIT` remains explicitly
inconclusive. The added through-58 cubic-bipartite exclusion and the existing
through-31, `P_13`-free, and structural results constrain novelty and useful
partial progress, not the unrestricted counterexample predicate. Consequently
the route-baseline changes do not narrow or broaden verifier authority, and the
manifest is unchanged from the red-teamed version.
