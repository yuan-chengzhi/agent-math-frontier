# OPEN_STATUS_AND_NOVELTY review: `aim-60-first-prime`

- Review date / source-access date: **2026-08-14**
- Frozen source revision reviewed: `aim-aint26-2026-05`
- Review scope: whether beating the frozen `x0 = 616980` example is still a novel finite target under `1 <= a < 10^20`
- Final verdict: **FAIL**

This is an evidence report only. It is not a receipt, an authority or session record, an activation, or an independent primality/factor certificate for any number quoted below.

## Frozen target reconstructed for this review

The target accepts a positive integer `a < 10^20` whose first prime value among positive inputs occurs at an integer `616981 <= x0 <= 10000000`. It deliberately claims only a certified finite instance beyond the AIM document's displayed example `a=488669, x0=616980`, not the current world record or the global optimum.

## Current primary and public evidence

| Source | Date/revision visible on source | Observation on 2026-08-14 |
|---|---|---|
| AIM workshop problem list, <https://aimath.org/pastworkshops/aint26problemlist.pdf> | May 2026 | Problem 60 asks for `a < 10^20` maximizing the least positive `x` for which `x^12+a` is prime. It gives `a=488669, x=616980` as an **example** and says no `a < 10^6` does better. It does not say 616980 is best over `a < 10^20`. |
| OEIS A122131, <https://oeis.org/A122131> | Entry current on access date; comments dated 2016 and 2022 | Confirms that 616980 is the first listed positive `n` for which `n^12+488669` is prime and records the divisibility restrictions by `2,3,5,7,13`. It concerns fixed `a=488669`, not optimization over `a`. |
| Prime Puzzles, Puzzle 855, <https://www.primepuzzles.net/puzzles/puzz_855.htm> | Public page indexed and accessed through current search on 2026-08-14; the page does not expose a reliable publication/revision date | Publishes several stronger degree-12 examples. In particular its table gives `a=2252249, x0=655200`; `a=2459729, x0=769860`; `a=7676759, x0=1427790`; and `a=26060579, x0=1455090`. It also states `x^12+3480749` is composite before `x0=925470` and prime there. All these positive constants are below `10^20`, and all quoted first-prime indices fall inside the target's 10,000,000 cap. |

Prime Puzzles is not a maintained research-record authority and this review has not independently certified every predecessor. That limitation does not rescue the frozen novelty threshold: an explicit, checkable public claim inside the target domain is already enough to create a duplicate conflict, and multiple such claims are present.

## Searches performed

Web searches were run on 2026-08-14 with these literal query strings:

- `"488669" "616980"`
- `"x^12+a" "488669"`
- `"x^{12}+a" first prime 616980`
- `AIM problem 60 aint26 first prime x^12+a`
- `site:primepuzzles.net/puzzles/puzz_855.htm "1427790"`
- `site:primepuzzles.net/puzzles/puzz_855.htm "26060579"`
- `"x^12 + 7676759" 1427790`
- `"x^12 + 26060579" 1455090`
- `"first prime" "x^12" "a" 1455090`
- `"least value of x" "x12 + a" prime`
- `"a < 10^20" "x^12" prime`

I opened the AIM PDF, OEIS entry, and the current indexed content of Puzzle 855. I did not locate an authoritative maintained leaderboard or a proof of the optimum over `a < 10^20`; therefore 1,455,090 is a **known public lower benchmark found in this review**, not asserted here to be the current record.

## Status drift, stronger results, and conflicts

- The AIM optimization problem remains open: no global maximizing `a` was found in the sources reviewed.
- The repository's 616980 threshold is nevertheless stale for **novelty**. The AIM source itself only makes an optimality statement for `a < 10^6`; the target allows `a < 10^20`. Public examples with `a > 10^6` already beat 616980.
- The target can be satisfied immediately in mathematical content by reconstructing a certificate for a published Puzzle 855 example. That could be useful verifier/baseline work, but it is reproduction, not a new record or a new finite instance.
- The absence of a reliable date/revision label on Puzzle 855 is a provenance weakness and should be preserved as such. Its explicit numerical claims remain a blocking duplicate risk that can be settled by the target's own exact checker.

## Duplicate and variant risks

1. **Displayed example versus record.** `a=488669` is best only under the source's stated `a < 10^6` comparison. It is not presented as best under `a < 10^20`.
2. **Positive versus arbitrary integer `a`.** The frozen target restricts to positive `a`; the AIM line merely says “value of `a < 10^20`.” This is primarily a statement-fidelity issue, but public stronger examples above are positive, so it does not affect the duplicate finding.
3. **Positive input versus including zero.** Some Puzzle 855 prose counts composites from `x=0`; the listed first positive prime indices are still valid only if every `1 <= x < x0` is composite and `x0` is prime. A future certificate must check exactly that domain.
4. **Probable prime versus certified prime.** A historical PRP report is not enough for this target. This affects verification strength, not the fact that the public candidate is prior art requiring investigation.
5. **Finite improvement versus optimum.** Even a genuinely new `x0` would be only a lower-bound/record candidate unless optimality over all allowed `a` were separately proved.

## Exact modest claim currently permitted

Under the unchanged frozen threshold, an accepted artifact may claim only:

> The checker certifies a positive `a < 10^20` whose first positive prime value occurs after the specifically frozen AIM example at 616980.

It may **not** claim novelty, a current record, the best known `a`, or progress beyond public degree-12 examples unless the accepted `x0` exceeds a newly researched and independently confirmed public baseline. Certifying one of the Puzzle 855 constants would properly be described as an independent reconstruction or verifier regression.

## Required remediation for a future pass

Either:

1. reclassify this package explicitly as a non-novel reproduction/evaluator benchmark outside the `OPEN_STATUS_AND_NOVELTY` pass gate; or
2. perform a broader record search, independently certify the strongest public in-domain examples, and freeze a threshold strictly above the resulting baseline. On evidence found here, that threshold must be **at least 1,455,091**, but this review does not establish that 1,455,090 is the true current record.

## Verdict

**FAIL.** The root AIM optimization question is open, but the target's own success condition is already met by multiple public, in-domain degree-12 examples. Disclaiming a record claim prevents overstatement; it does not make a known finite instance novel. The target must not receive an `OPEN_STATUS_AND_NOVELTY` pass without rebasing or explicit non-novel reclassification.
