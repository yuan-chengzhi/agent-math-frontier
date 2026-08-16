# OPEN_STATUS_AND_NOVELTY review: `degree-diameter-3-9-record`

- Review date / source-access date: **2026-08-14**
- Frozen source revision reviewed: `degree-diameter-table-2026-08-13`
- Review scope: whether a graph accepted by the frozen target would still be a novel `(maximum degree, diameter) = (3,9)` record, and what may be claimed from it
- Final verdict: **PASS**

This is an evidence report only. It is not a receipt, an authority or session record, an activation, or a mathematical endorsement of any future candidate.

## Frozen target reconstructed for this review

The target asks for one finite, simple, undirected, connected graph on `n >= 601` vertices, with maximum degree at most `3` and diameter at most `9`. The `1534`-vertex input cap is the Moore bound, not a claimed attainable upper bound. Cubic regularity is not required.

## Current primary and maintainer evidence

| Source | Date/revision visible on source | Observation on 2026-08-14 |
|---|---|---|
| Francesc Comellas, maintained Degree-Diameter Table, <https://web.mat.upc.edu/francesc.comellas/delta-d/taula_delta_d.html> | Page says “Last changed: August 13, 2026”; latest-update list includes August 2026 entries | The table defines a `(Delta,D)` graph using **maximum** degree `Delta` and diameter at most `D`. Its row `Delta=3`, column `D=9` still gives **600**. The update log has no later `(3,9)` entry. |
| Maintainer's diameter-9 detail page, <https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g9.html> | Detail page says last modification June 22, 2025 | Lists `Exoo_600`, degree 3, diameter 9, order 600, Moore bound 1534, with an adjacency-list download. |
| Francesc Comellas, Mendeley dataset V11, DOI landing page <https://data.mendeley.com/datasets/d75dzbjd4k/11> | Published January 28, 2026 | Describes the dataset as the state-of-the-art table as of January 2026 and uses the same maximum-degree/at-most-diameter convention. This is older than the live August table but independently anchors the maintained dataset. |
| Francesc Comellas, “Table of large graphs with given degree and diameter,” <https://arxiv.org/abs/2406.18994> | v2, January 24, 2026 | Primary maintainer paper for the updated table. It does not advertise a replacement for the live table's 600 entry. |
| Maintainer directory index, <https://web.mat.upc.edu/francesc.comellas/delta-d/> | Accessed 2026-08-14 | Confirms the table and detail directories remain live; the live table, rather than an old mirrored table, was used for the verdict. |

The live maintainer table is the strongest status evidence here: it was updated one day before this review, contains other August 2026 changes, and nevertheless retains 600 at `(3,9)`.

## Searches performed

Web searches were run on 2026-08-14 with these literal query strings:

- `site:web.mat.upc.edu/francesc.comellas/delta-d (3,9) 600 degree diameter graph`
- `"(3, 9) graph" 600 601 degree diameter`
- `"(3,9)-graph" 600 degree diameter`
- `"degree 3" "diameter 9" 601 graph`
- `degree diameter graph 3 9 Exoo 600 record 2026`

I also opened the live table, its `(3,9)` detail page, the maintainer's current arXiv record, and the DOI-versioned dataset. No public graph of order at least 601 satisfying the same convention was found. Search hits involving generalized quadrangles `GQ(3,9)`, Ramsey `(3,9)`-graphs, cages of girth 9, or small graphs whose order/degree/diameter happen to contain the same numerals are different problems.

## Status drift, stronger results, and conflicts

- **No adverse status drift found.** The live table has changed repeatedly in 2026 and was last changed on 2026-08-13, but the `(3,9)` cell remains 600.
- The source detail page is older than the table and the archived dataset is from January. That date mismatch is not a substantive conflict because the newer live table still links the same 600 detail entry.
- The maintainer table is a “largest known” ledger, not a proof that 600 is optimal. The gap from 600 to the Moore bound 1534 remains large.
- Absence from search is not a priority guarantee. A construction may have been privately communicated, submitted, or posted under terminology not indexed by search engines. The table must therefore be checked again immediately before an attack and before any submission or publicity.

## Duplicate and variant risks

1. **Maximum degree versus regularity.** The maintained problem uses maximum degree at most 3. A valid nonregular graph must not be rejected merely because it is not cubic. Conversely, a result for cubic/vertex-transitive/Cayley graphs alone must not be described as the unrestricted degree-diameter record unless its explicit graph also satisfies the unrestricted target and exceeds 600.
2. **Diameter at most versus exactly.** A graph of diameter below 9 is valid. Literature on graphs of exactly diameter 9 may omit valid constructions.
3. **Connectedness.** Diameter in the maintained table is an all-pairs finite distance, so the target correctly requires connectedness.
4. **Other `(3,9)` notation.** Cage order `n(3,9)`, Ramsey graphs, and `GQ(3,9)` are unrelated and cannot establish novelty here.
5. **Record versus optimum.** An order-601 graph improves a lower bound/largest-known construction; it does not determine the maximum possible order.

## Exact modest claim permitted

If an explicit `n >= 601` graph is independently accepted and a same-day status check still shows no equal-or-larger prior construction, the permissible claim is:

> An explicit graph establishes `N(3,9) >= n` and improves the maintained largest-known `(maximum degree 3, diameter at most 9)` construction from 600 to at least `n`.

It may **not** be called an optimal graph, a solution of the degree-diameter problem for `(3,9)`, a proof that `N(3,9)=n`, or necessarily a cubic/regular record unless regularity is separately checked and that restricted record is separately researched.

## Verdict

**PASS.** As of 2026-08-14, the most current maintainer source still gives 600, the target's 601 threshold is a strict record-improvement threshold under the same convention, and no stronger matching construction was located. This pass is time-sensitive: novelty must be rechecked against the live table and direct maintainer channel at candidate-promotion and submission time.

## Final-card and agent-brief recheck

- Date: **2026-08-14**
- Final target-card raw SHA-256: `bdd8f93bcc0fac09eb2a06fff262525b96e92c86486acba50484cd7189d74391`
- Agent baseline brief raw SHA-256: `4083eb739058d13e5969e6ed444529c87827a4e4f259e211dff87bed4be1ba0b`
- Result: **PASS**

The final card preserves the exact record-improvement scope: order at least 601 against the maintained order-600 baseline, with maximum degree at most 3 and diameter at most 9, and it requires a fresh novelty review rather than claiming optimality. The agent brief and `data/problems.json` accurately retain the order-600 record and the licensing boundary from the provenance audit: the outer dataset is labelled CC BY 4.0, but file-level third-party redistribution rights remain unclear, so the repository must not bundle the raw or complete normalized `Exoo_600` graph without permission. No status or novelty language has been upgraded.
