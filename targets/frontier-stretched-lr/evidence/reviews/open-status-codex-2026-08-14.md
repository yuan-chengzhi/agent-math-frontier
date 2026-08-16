# OPEN_STATUS_AND_NOVELTY review: `frontier-stretched-lr`

- Review date / source-access date: **2026-08-14**
- Frozen source revision reviewed: `frontiermath-page-2026-08-14`
- Review scope: current status of the bounded Epoch prompt and the broader King–Tollu–Toumazet monomial-coefficient positivity conjecture
- Final verdict: **PASS**

This is an evidence report only. It is not a receipt, an authority or session record, an activation, or a correctness review of a future polynomial.

## Frozen target reconstructed for this review

Using the target convention

`P(t) = c^(t*lambda)_(t*mu,t*nu)`,

the task is to give three nonempty partitions, each of length at most 7 and size at most 30, with `|lambda| = |mu| + |nu|`, for which a coefficient of `P(t)` in the ordinary monomial basis `1,t,t^2,...` is negative. The bounded prompt asks for one counterexample; it does not ask for minimality or a classification.

## Current primary and maintainer evidence

| Source | Date/revision visible on source | Observation on 2026-08-14 |
|---|---|---|
| Epoch AI, current problem page, <https://epoch.ai/frontiermath/open-problems/stretched-lr-coefficients> | Current page accessed 2026-08-14 | Labels the problem **Unsolved**, “Construction - Finite,” and “Counterexample.” The prompt gives exactly the length-at-most-7 and sum-at-most-30 bounds and asks for a negative ordinary polynomial coefficient. |
| Epoch AI background note, <https://epoch.ai/files/open-problems/stretched-lr-coefficients.pdf> | Current PDF accessed 2026-08-14 | States the broader King–Tollu–Toumazet nonnegativity conjecture, says it remains open with little progress, and asks for a negative coefficient. It also supplies the degree bound used by the frozen checker. |
| Alper Ferudun, “Positivity of stretched Littlewood–Richardson coefficients for partitions of length at most four,” <https://arxiv.org/abs/2607.22301> and HTML <https://arxiv.org/html/2607.22301> | Submitted July 24, 2026; manuscript displays August 11, 2026 | Proves coefficientwise nonnegativity when all three partitions have length at most 4. It additionally proves positivity of the top four coefficients for full-dimensional hives of any rank and, for full-dimensional five-part hives, all coefficients except possibly the linear coefficient. The paper explicitly says the general conjecture remains open. |

The Epoch page was live and still marked unsolved after the July preprint and on the review date. No public negative-coefficient triple satisfying the prompt was located.

## Searches performed

Web searches were run on 2026-08-14 with these literal query strings:

- `"stretched Littlewood-Richardson" negative coefficient conjecture 2025 2026`
- `"negative coefficient" "stretched Littlewood-Richardson"`
- `"negative coefficients" "Littlewood-Richardson polynomial"`
- `"King Tollu Toumazet" counterexample negative coefficient`
- `stretched LR polynomial nonnegative coefficients counterexample`

I opened the current Epoch page and PDF, the July 2026 arXiv abstract, and the full arXiv HTML. Search hits about Newell–Littlewood functions, Jack Littlewood–Richardson polynomials, stretched Schubert coefficients, arbitrary Ehrhart polytopes, weighted Ehrhart polynomials, or coefficients in an `h*`/binomial basis are variants and do not answer this monomial-basis LR question.

## Status drift, stronger results, and conflicts

- **Important partial-result drift:** arXiv:2607.22301 postdates much of the background narrative and completely removes the subrange in which all three partition lengths are at most 4. A future search or claimed partial exclusion that ignores this result would duplicate known work.
- The new preprint does **not** close the bounded Epoch prompt: the prompt permits lengths 5, 6, and 7. For full-dimensional five-part hives the preprint leaves the linear coefficient open, and it also identifies lower-dimensional five-part cases not covered by that theorem.
- The Epoch page and the preprint agree that the general positivity conjecture is unresolved. There is therefore no substantive open-status conflict.
- The arXiv result is a recent computer-assisted preprint, not treated here as a peer-reviewed final authority. It is nevertheless public primary evidence and must be treated as a novelty baseline unless superseded or refuted.

## Duplicate and variant risks

1. **Outer-partition notation.** Epoch and this target use `c^(t*lambda)_(t*mu,t*nu)`, while much of the literature, including arXiv:2607.22301, writes `c^(t*nu)_(t*lambda,t*mu)`. The two lower partitions are symmetric; the outer partition is not. Comparisons require an explicit relabelling, not a visual name match.
2. **Coefficient basis.** Only negativity in the ordinary monomial `t` basis meets the target. Negativity in a binomial, Newton, `h*`, or weighted-Ehrhart basis is not a counterexample.
3. **Polynomial versus quasi-polynomial/eventual polynomial.** Results for other stretched multiplicities can be quasi-polynomial or eventually polynomial. They do not duplicate an LR polynomial counterexample.
4. **Rational coefficients.** The conjecture is about nonnegative rational monomial coefficients; integrality must not be silently assumed.
5. **Known-positive subranges.** A purported counterexample with all three lengths at most 4 conflicts with the July theorem and demands resolution before any novelty claim. Search effort should begin with maximum length at least 5.
6. **Bounds belong to the Epoch task, not the global conjecture.** A candidate outside length 7 or size 30 could refute the global conjecture but would not solve this frozen bounded prompt.

## Exact modest claim permitted

If a bounded triple and its complete polynomial are independently verified and a submission-time search finds no prior triple, the permissible claim is:

> This explicit triple satisfies the 2026 Epoch bounded prompt and gives a counterexample to the King–Tollu–Toumazet conjecture that every stretched Littlewood–Richardson polynomial has nonnegative monomial coefficients.

Although the search window is bounded, one genuine negative coefficient would refute the unrestricted universal positivity conjecture. It would **not** establish the smallest counterexample, characterize all failures, or invalidate coefficient positivity in a different basis. A negative search result in the frozen bounds would establish at most a separately certified bounded exclusion, not the global conjecture.

## Verdict

**PASS.** The maintainer page still marks the exact bounded task unsolved, the current primary literature still calls the global conjecture open, and no matching counterexample was found. The July/August 2026 length-at-most-4 theorem is a mandatory novelty baseline but does not subsume the target. Promotion-time review must re-run the search and must resolve any candidate that falls in a known-positive subrange.

## Final-card and agent-brief recheck

- Date: **2026-08-14**
- Final target-card raw SHA-256: `1ab87748125aa10d24229cadc47c8d04a99add70aeb42465b8be8232b458aad8`
- Agent baseline brief raw SHA-256: `08315fc967058c2f8cd5cdc2189b7dd6c758db71d133d6bf938c45050db553e8`
- Result: **PASS**

The final card, agent brief, and `data/problems.json` all preserve the exact known-positive boundary: every monomial coefficient is nonnegative when all three partitions have length at most 4, so a novel counterexample search must have maximum partition length at least 5. The brief also retains the narrower full-dimensional five-part qualification rather than generalizing it. The bounded task and global conjecture remain described as open, and neither a bounded exclusion nor a candidate has been promoted into an unsupported novelty or resolution claim.
