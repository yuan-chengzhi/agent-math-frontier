# Statement-fidelity review: Erdős Problem 64

Date checked: 2026-08-14

Verdict: **PASS** for the graph-counterexample acceptance route. This verdict does not establish current open status, novelty, verifier implementation soundness, or any positive proof route.

## Materials checked

- The canonical [Erdős Problems #64](https://www.erdosproblems.com/64) statement as indexed on 2026-08-14: every finite graph of minimum degree at least 3 should contain a cycle of length `2^k` for some `k >= 2`.
- The pinned Formal Conjectures source at revision `b33d8678a28118c95d8d4f60b11faaf39ccff1e6`, declaration `Erdos64.erdos_64`. Freshly retrieved bytes had SHA-256 `36b7a400cd21197e602deb279c771cbf7b6e13ce3d070c6276848b23d00b981a`, exactly matching the local snapshot.
- `target-card.json`, `candidate.schema.json`, the target README, baseline source metadata, and the semantic input/acceptance path of the graph checker.

## Quantifiers and graph conventions

The source is universal over finite graphs with minimum degree **at least** 3. The Formal Conjectures snapshot makes the usual graph convention precise with `SimpleGraph V` and a finite vertex type. The target's labelled vertex set `{0,...,n-1}` and canonical undirected edge list are merely a finite representation of the same objects. The checker applies a lower degree bound; it does not replace minimum degree at least 3 by cubic regularity.

Connectivity is correctly not required. The source quantifies over all finite simple graphs, including disconnected ones. A disconnected finite simple graph whose every vertex has degree at least 3 and which has no relevant cycle would still refute the universal conjecture. Requiring connectivity would be an unjustified strengthening of a candidate witness.

The exponent condition is correctly read as natural `k >= 2`, hence forbidden simple-cycle lengths are

```text
4, 8, 16, 32, 64, ...
```

For a graph on at most 64 vertices, only the listed lengths not exceeding `n` can occur. Exhaustively checking those lengths is therefore exhaustive for that particular candidate; no omitted larger power of two can be the length of a simple cycle in it.

The lower order bound `n >= 4` loses nothing, since a finite simple graph with minimum degree at least 3 has at least four vertices.

## Representation cap and logical direction

The upper interface bound `n <= 64` is not asserted as a counterexample-size theorem. It limits which explicit witnesses this V1 checker accepts. If a graph inside that bound is accepted, it is a counterexample to the unrestricted universal statement and therefore a full disproof, irrespective of how the witness was found. Conversely, an exhaustive search that finds no candidate up to 64 proves neither the conjecture nor the nonexistence of a larger counterexample.

The target card, README, success criterion, and apparatus-error rule preserve this asymmetry. In particular, hitting the cycle-search step ceiling is inconclusive, not mathematical rejection. `claim_scope = FULL_PROBLEM` is faithful only in this acceptance sense: a verified counterexample settles the full problem negatively. Interfaces presenting this field should retain the nearby "if accepted" qualification.

The partial-progress criterion correctly keeps subclass theorems, larger finite exclusions, structural restrictions, and Lean lemmas below root closure. Those results may be valuable without proving or disproving the universal statement.

## Checks performed

The targeted tests confirmed the exact forbidden lengths through the 64-vertex boundary, minimum-degree semantics, the absence of a connectivity requirement, and agreement with an independent brute-force cycle reference on small graphs. They also confirmed that search-budget exhaustion is classified as an apparatus failure. These checks support the semantic mapping but are not a verifier red-team review.

No statement-fidelity correction is required. Any future positive-proof/Lean closure path needs its own statement and trust-boundary review; the present target correctly does not accept one.

## Final-card recheck

Date: 2026-08-14. **PASS.** Final `target-card.json` raw-file SHA-256: `106f5e6d4ad516a7eee5e38e43244769dc5254ce10d357505c90c853dc53fbcd`. Its `problem_card_sha256` value, `a75b3beccdf71f86bc425cecfe1485b82e849174ca528abf2351a4915f51b4e9`, matches a fresh canonical-hash computation of the corresponding `data/problems.json` entry. The final literature-baseline edit adds known finite and subclass exclusions to partial-progress guidance only; it does not change the universal graph statement, the counterexample acceptance direction, or the `FULL_PROBLEM` claim scope.
