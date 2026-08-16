# OPEN_STATUS_AND_NOVELTY review: `erdos-64`

- Review date / source-access date: **2026-08-14**
- Frozen formal source revision reviewed: `b33d8678a28118c95d8d4f60b11faaf39ccff1e6`
- Review scope: current status of the unrestricted finite Erdős–Gyárfás conjecture and novelty implications for an explicit counterexample on at most 64 vertices
- Final verdict: **PASS**

This is an evidence report only. It is not a receipt, an authority or session record, an activation, or an audit of the graph checker.

## Frozen target reconstructed for this review

The target asks for a finite simple undirected graph on `4 <= n <= 64` vertices, minimum degree at least 3, and no simple cycle of length `2^k` for any integer `k >= 2`. In this order range the relevant lengths are 4, 8, 16, 32, and (only at `n=64`) 64. One accepted graph is a counterexample to the unrestricted universal conjecture; the order cap limits representation and search, not the mathematical force of a found counterexample.

## Current maintainer and primary evidence

| Source | Date/revision visible on source | Observation on 2026-08-14 |
|---|---|---|
| Erdős Problems #64, <https://www.erdosproblems.com/64> | Page says last edited April 10, 2026; current search result accessed 2026-08-14 | Marks the problem **FALSIFIABLE / Open** and states the finite minimum-degree-at-least-3 conjecture. It distinguishes the still-open root conjecture from the now-refuted stronger belief that counterexamples should exist at every large minimum degree. |
| Formal Conjectures current file, <https://github.com/google-deepmind/formal-conjectures/blob/main/FormalConjectures/ErdosProblems/64.lean> and raw <https://raw.githubusercontent.com/google-deepmind/formal-conjectures/main/FormalConjectures/ErdosProblems/64.lean> | Current `main` accessed 2026-08-14 | Still labels `Erdos64.erdos_64` as `research open`; its theorem body remains `sorry`. This agrees with, but does not independently prove, the open status. |
| Hegde, Sandeep, Shashank, “Erdős-Gyárfás conjecture on graphs without long induced paths,” <https://arxiv.org/abs/2410.22842> | v2, February 11, 2025 | Proves the conjecture for `P_13`-free graphs with computer assistance; explicitly a subclass result. |
| Avery Carr, “Every Minimal Counterexample to the Erdős-Gyárfás Conjecture is Predominantly Cubic,” <https://arxiv.org/abs/2605.22844> and HTML <https://arxiv.org/html/2605.22844> | v1, May 13, 2026 | Says the general conjecture remains open. Gives structural constraints on a minimum-order/minimum-size counterexample, including domination by degree-3 vertices, independence of degree-at-least-4 vertices, and the `4/7` cubic-vertex lower proportion. |
| Balaji, public SAT/SMS repository pinned by the target, <https://github.com/ArjunBalaji79/erdos-gyarfas-min-degree-3/tree/c8c11e234d49baa263236a924789d3087e70b5c7> | Pinned 2026 repository; says work is under review | Claims exhaustive exclusion of all minimum-degree-at-least-3 counterexamples through 31 vertices, hence a public general lower bound `n >= 32`. It is computational/public evidence, not treated here as a peer-reviewed theorem or a review receipt. |
| Julius Tranquilli, “A 60-Vertex Lower Bound for Cubic Bipartite Counterexamples to the Erdős-Gyárfás Conjecture,” <https://arxiv.org/abs/2608.02675> and HTML <https://arxiv.org/html/2608.02675> | v1, August 2, 2026 | Proves by certified exhaustive computation that every simple cubic bipartite graph on at most 58 vertices has a 4-, 8-, or 16-cycle. Thus a cubic bipartite counterexample has at least 60 vertices. The paper explicitly says the unrestricted conjecture remains open. |

The maintainer page predates the May and August 2026 papers, but every newer primary source reviewed still describes the unrestricted conjecture as open. No explicit unrestricted counterexample was found.

## Searches performed

Web searches were run on 2026-08-14 with these literal query strings:

- `site:erdosproblems.com/64 Erdős #64 open`
- `site:github.com/teorth/erdosproblems "64" "power of 2"`
- `site:arxiv.org Erdős-Gyárfás conjecture 2026`
- `"Erdős-Gyárfás conjecture" counterexample 2025 2026`
- `Erdos Gyárfás conjecture power of two cycle lengths 2026 counterexample`

I opened the maintainer page, current Formal Conjectures file, the `P_13` paper, both 2026 structural/computational preprints, and the pinned SAT repository. Search hits for the monochromatic path-cover conjecture of Erdős and Gyárfás are a different conjecture.

## Status drift, stronger results, and conflicts

- **Root status:** no drift found. The unrestricted finite-graph conjecture remains open in the maintainer database, current formalization, and newer primary papers.
- **Route-baseline drift:** arXiv:2608.02675 is newer than the route baselines listed in the target's source metadata and raises the cubic-bipartite exclusion frontier to 58 vertices. It must be cited before claiming any cubic-bipartite finite exclusion or search progress in this target range.
- The August result does not exclude non-bipartite cubic graphs or nonregular graphs of minimum degree at least 3, so it does not subsume the full target.
- The public through-31 SAT result is broader by graph class but weaker by order. Its repository wording has minor historical/about-text inconsistencies (`<=30`, `<=31`, and the resulting lower-bound phrasing appear in different parts); the pinned README's detailed table claims UNSAT for every `n=17,...,31`. Treat it as a public computational baseline pending independent reproduction.
- The large-minimum-degree theorem cited by the Erdős Problems page disproves the stronger expectation of counterexamples for every minimum degree `r`; it does not prove the minimum-degree-3 conjecture.

## Duplicate and variant risks

1. **Finite versus infinite.** An infinite 3-regular tree has no cycles but is irrelevant; the conjecture and target concern finite graphs.
2. **Minimum versus average/maximum degree.** The hypothesis is minimum degree at least 3. Results using average degree or maximum degree answer different questions unless they imply this hypothesis.
3. **Simple cycles and all powers.** Avoiding only 4- and 8-cycles is insufficient once 16 vertices are allowed; at the top of this target all of 4, 8, 16, 32, and 64 matter.
4. **Subclass exclusions.** `P_13`-free, planar, cubic bipartite, Cayley, diameter-2, or other family results cannot be promoted to the unrestricted theorem.
5. **Disconnected candidates.** Connectivity is not required by the conjecture. A disconnected accepted graph would still be a valid counterexample (and one of its minimum-degree-at-least-3 components would itself be a connected counterexample).
6. **Bounded failure versus disproof.** Failure to find a graph with `n <= 64`, or a checker rejection/timeout, is not evidence that the global conjecture is true. An exhaustive independently certified all-graph exclusion would be only a new lower bound on counterexample order.

## Exact modest claim permitted

If one explicit graph in the frozen range is independently accepted and a submission-time novelty search finds no prior graph, the permissible claim is:

> This finite graph is a counterexample to the unrestricted Erdős–Gyárfás conjecture, and therefore disproves Erdős Problem #64 as stated.

This is a full disproof, not merely a “bounded version,” because the original statement is universal over all finite graphs. The modesty constraints are elsewhere: do not claim minimal order, uniqueness, connectedness, a family of counterexamples, or anything about arbitrarily large minimum degree without separate proof. If no graph is found, claim only the exact independently certified finite or subclass exclusion actually performed.

## Verdict

**PASS.** Current maintainer and primary sources agree that the unrestricted conjecture is open, and no prior matching counterexample was found. The recent cubic-bipartite lower bound is meaningful status drift for search strategy and partial-progress novelty, but it does not close or duplicate the full explicit-counterexample target. Any future promotion must refresh the fast-moving 2026 computational literature and compare an actual candidate graph directly.

## Final-card and agent-brief recheck

- Date: **2026-08-14**
- Final target-card raw SHA-256: `106f5e6d4ad516a7eee5e38e43244769dc5254ce10d357505c90c853dc53fbcd`
- Agent baseline brief raw SHA-256: `6afd9050a4b38a91a52fe3173f66498a5fb6f9eb006547b064f8a121c9d17f41`
- Result: **PASS**

The final card, agent brief, and `data/problems.json` correctly distinguish the unrestricted open conjecture from finite and subclass baselines. They retain the public all-graph exclusion through 31 and the certified simple cubic-bipartite exclusion through 58, without converting the latter into an unrestricted order-60 lower bound or extending it to non-bipartite cubic or nonregular graphs. A bounded negative search remains explicitly non-closing, and no status or novelty language has been upgraded.
