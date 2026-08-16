# Independent verifier red-team: degree--diameter (3,9)

Date: 2026-08-14  
Reviewer: `codex-verifier-red-team-2026-08-14`  
Verifier: `amf.dd39.exact.v1`  
Verdict: **PASS AFTER REMEDIATION**

This is a verifier-engineering assessment, not a red-team receipt, reviewer
authority record, novelty review, or claim that a 601-vertex graph exists.

## Boundary audited

The accepted object must be a strict JSON edge list for a simple undirected
graph with `601 <= n <= 1534`, maximum degree at most three, connectivity, and
all-pairs diameter at most nine. Cubic regularity is deliberately not required.
The dispatcher must run the queue-BFS and bit-set-wavefront cores on one byte
snapshot, require exact agreement, and distinguish mathematical rejection from
apparatus failure.

The source set audited after remediation is bound by manifest SHA-256
`4867432412b67c84c6705d00808b6bfbdb9a02a3de6acddc86093055a8779705`.

## Finding and remediation

### DD-RT-01: resource failures could be recorded as mathematical rejection

Severity: medium for ledger integrity; no false-accept path.

Before remediation, each core caught `MemoryError`/`OverflowError`, emitted
`RESOURCE_FAILURE`, and exited 1. If both cores failed the same way, the
dispatcher could agree on that output and the host would classify the run as a
normal rejected artifact. This loses the distinction between “the graph fails
the target” and “the checker did not establish anything.”

The cores now expose `evaluate_path_with_status`, exit 2 on resource failure,
and retain the old in-process result wrapper. The dispatcher accepts exit 2 only
as infrastructure, returns `CHECKER_INFRASTRUCTURE_FAILURE`, rejects a forged
exit-1 `RESOURCE_FAILURE`, and checks that accepted facts themselves satisfy the
order, degree, connectivity, edge-count, and diameter envelope. Manifest and
registry byte bindings were updated to the remediated source.

## Adversarial evidence

- Exhausted all 1,099 labelled simple graphs of orders one through five. Both
  cores agreed exactly with a third queue-BFS implementation on maximum degree,
  connectivity, diameter, reason code, and acceptance at the explicit
  small-order test seam.
- Checked the sharp diameter boundary with paths `P10` and `P11`; `P10` has
  maximum degree two and diameter nine, while `P11` is rejected for diameter.
  This also confirms that “maximum degree at most three” was not replaced by
  cubic regularity.
- Attacked Boolean and floating vertices, duplicate nested JSON keys, reversed
  edges, duplicate edges, large output, checker timeout, forged accepted facts,
  exit-code/result disagreement, and exit-1 resource claims. No attack crossed
  the dispatcher as acceptance.
- Replaced content-bound source bytes and then replaced a checker with a
  symlink inside a copied repository. The manifest contract rejected both.

The dedicated red-team suite contains 9 test methods covering 14 frozen corpus
classes and passed 9/9. The repository suite after remediation passed 115/115.

## Independence assessment

The mathematical cores are meaningfully different: one performs all-pairs
queue BFS over adjacency lists; the other expands bit-set wavefronts. They own
separate parsers and graph construction code and execute in separate isolated
Python processes. They still share the target statement, Python runtime, input
snapshot, and dispatcher. The dispatcher/manifest boundary is therefore
security-relevant and cannot be replaced by mere agreement of two unpinned
scripts.

## Residual limits and claim ceiling

- No production-positive graph with at least 601 vertices was available. The
  acceptance boundary is exercised by explicit test seams, while the frozen
  600-vertex graph is correctly measured and rejected by the production order
  threshold.
- The tests establish checker soundness evidence, not that the public record is
  still 600, not novelty, and not publication significance.
- Static source drift and symlink substitution are rejected. The host must also
  run the pinned source checkout read-only between validation and execution;
  adversarial concurrent mutation of the verifier repository is outside this
  target process and belongs to host sandboxing.
- Worst-case performance at the full Moore bound requires a separate budget
  receipt. A timeout remains inconclusive.

Within those explicit limits, no false accept was found and the remediated
verifier is suitable for exact checking of the frozen target.

## Final-card recheck

Date: 2026-08-14  
Final target-card SHA-256: `bdd8f93bcc0fac09eb2a06fff262525b96e92c86486acba50484cd7189d74391`  
Current verifier-manifest SHA-256: `4867432412b67c84c6705d00808b6bfbdb9a02a3de6acddc86093055a8779705`  
Verdict: **PASS**

The final card retains exactly the red-teamed acceptance boundary: a canonical
simple connected graph with `601 <= n <= 1534`, maximum degree at most three,
and diameter at most nine, accepted only after the queue-BFS and bit-set cores
agree. The licensing revision removes redistribution of the third-party
600-vertex baseline and retains only provenance, hashes, derived measurements,
and a local conversion path. That graph is below the production threshold and
is not verifier source or candidate evidence, so the license/provenance change
does not weaken or enlarge the mathematical acceptance claim. Record novelty
remains outside verifier authority as stated in the final card.
