# Statement-fidelity review: degree--diameter (3,9)

Date checked: 2026-08-14

Verdict: **PASS** for statement fidelity. This verdict does not certify current novelty at a later launch date, verifier implementation independence, artifact licensing, or a submitted graph.

## Materials checked

- The maintainer's [degree--diameter table](https://web.mat.upc.edu/francesc.comellas/delta-d/taula_delta_d.html), which defines the degree of a graph as its maximum vertex degree, defines a `(Delta,D)` graph using degree/diameter caps, and listed order `600` at `(3,9)` when checked. The page said it was last changed on 2026-08-13.
- The maintainer's [diameter-9 description](https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g9.html), which identifies `Exoo_600` as degree 3, diameter 9, order 600, with Moore bound 1534.
- The maintainer-hosted `Exoo_600.txt`. Freshly retrieved bytes had SHA-256 `12de7e2c303955f57196888a0eecae17d7e872616a638d6f7772b09f77f34106`, equal to the frozen artifact and metadata.
- `target-card.json`, `candidate.schema.json`, the target README, the frozen normalized baseline, and the semantic acceptance paths in both checker implementations.

## Quantifiers and conventions

The source problem asks for a largest possible finite undirected graph subject to maximum degree and diameter bounds. The frozen campaign target asks for one explicit graph satisfying

```text
n >= 601, maximum degree <= 3, diameter <= 9.
```

That is exactly a strict improvement over the source table's frozen order-600 entry. Connectivity is correctly required: ordinary finite graph diameter is finite only for a connected graph, and both implementations explicitly reject a disconnected candidate. A strict canonical simple edge list is a representation choice consistent with the simple undirected graphs used by the table, not an added mathematical shortcut.

The target says "maximum degree at most 3" rather than requiring cubic regularity. This is the correct degree--diameter convention and avoids silently replacing the problem by a cubic-graph problem. Even if the table's prose "maximum degree 3" were read as equality, there is no acceptance gap here: a connected graph of maximum degree at most 2 is a path or cycle, and diameter at most 9 limits its order to at most 19. Thus every accepted graph of order at least 601 necessarily has maximum degree exactly 3, without requiring every vertex to have degree 3.

The upper representation bound is not a substantive restriction. The Moore bound is

```text
1 + 3(1 + 2 + ... + 2^8) = 1534,
```

so no graph satisfying the mathematical `(3,9)` constraints can have more than 1534 vertices. The edge-list cap is likewise compatible with maximum degree 3.

## Success, partial progress, and claim ceiling

Acceptance establishes the existence of a graph strictly larger than the frozen 600-vertex entry. It does not prove optimality and does not make the graph a current record unless a separate, contemporaneous status search finds no intervening construction. `claim_scope = RECORD_IMPROVEMENT`, the separate novelty-review requirement, and the stop condition for a changed table preserve that distinction.

The partial-progress clause is also faithful: improvements within a construction family, candidates below 601, or pruning results may be useful but cannot satisfy this frozen record-improvement target.

## Checks performed

The targeted test suite reproduced the frozen graph as order 600, 900 edges, maximum degree 3, connected, and diameter 9 in both implementations. It also confirmed that the production threshold rejects order 600, that maximum degree is not confused with cubic regularity, and that radius 9 is not confused with diameter 9. These checks support the semantic mapping but are not a verifier red-team review.

No statement-fidelity correction is required. At activation and submission time, the table must still be rechecked because the record is explicitly time-dependent.

## Final-card recheck

Date: 2026-08-14. **PASS.** Final `target-card.json` raw-file SHA-256: `bdd8f93bcc0fac09eb2a06fff262525b96e92c86486acba50484cd7189d74391`. Its `problem_card_sha256` value, `ff24ae26ddc2206625a765c5a67ff9bc7c360c42f0067ac4c2cff5aa4444eb73`, matches a fresh canonical-hash computation of the corresponding `data/problems.json` entry. The final literature and redistribution-license baseline edits affect provenance, current-record review, and risk handling only; they do not change the quantified graph conditions or `RECORD_IMPROVEMENT` claim scope reviewed above.
