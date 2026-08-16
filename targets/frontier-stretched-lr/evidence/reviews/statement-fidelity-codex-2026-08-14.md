# Statement-fidelity review: stretched Littlewood--Richardson coefficients

Date checked: 2026-08-14

Verdict: **PASS** for statement fidelity. This verdict does not establish current open status, verifier soundness, implementation independence, or the existence of a successful candidate.

## Materials checked

- The official Epoch AI [problem page](https://epoch.ai/frontiermath/open-problems/stretched-lr-coefficients), including its bounded prompt as displayed on 2026-08-14.
- The official [background PDF](https://epoch.ai/files/open-problems/stretched-lr-coefficients.pdf). Freshly retrieved bytes had SHA-256 `135f583c5d6edacf1251624f5f0aaad1b85190bab5a7703173b1ba84e36d8052`, matching the hash recorded in the target README.
- `target-card.json`, `candidate.schema.json`, `evidence/regression/cases.json`, the target README, and the semantic input/acceptance paths of both exact implementations.

## Roles, order, and partition bounds

The operative prompt uses

```text
c^(t*lambda)_(t*mu,t*nu), with |lambda| = |mu| + |nu|,
```

so `lambda` is the outer partition and `mu`,`nu` are the two inner partitions. The target, schema, facts, direct-tableau implementation, and Jacobi--Trudi/Pieri implementation all use this ordering. This matters because the introductory prose on the web page also displays the generic convention `c^(t*nu)_(t*lambda,t*mu)`; that generic relabelling must not override the symbols in the actual prompt. The current target follows the prompt and the PDF correctly.

The web prompt says that **each** partition has length at most 7 and sum of parts at most 30. The target applies both bounds separately to all three partitions. Canonical weakly decreasing positive-part lists are the standard finite representation of integer partitions.

The target excludes empty partitions, although the prompt does not explicitly discuss the empty partition. This does not exclude a possible negative-coefficient witness. If an inner partition is empty, the LR coefficient is a Kronecker-delta case and its stretch is identically 0 or 1; if the outer partition is empty, the size equation forces both inner partitions to be empty. None of these cases has a negative coefficient.

## Polynomial certificate

The official PDF states the safe bound

```text
degree P <= binomial(length(lambda) + 1, 2).
```

For `length(lambda) <= 7`, this is at most 28. Consequently 29 exact values at the distinct positive integers `t=1,...,29` uniquely determine the polynomial over the rationals. Sampling only positive `t` also avoids relying on an implementation-specific convention for scaling every partition by zero.

The source asks only for the three partitions. Requiring the complete polynomial and its 29 exact evaluations is an additional certificate requirement, not a restriction on the mathematical witness: those data are uniquely determined by any valid triple. Encoding power-basis coefficients as reduced rational pairs is also faithful. An integer-valued polynomial need not have integral monomial coefficients, and neither the prompt nor the background PDF licenses an integrality assumption.

The coefficient list is constant term first, and "at least one negative coefficient" is applied to the complete power-basis polynomial. This matches the source's coefficient-positivity question; it is not merely negativity in a Newton, binomial, or sampled-value basis.

## Success, partial progress, and claim ceiling

An accepted triple would solve the bounded Epoch prompt and would supply a counterexample to monomial-coefficient nonnegativity for stretched LR polynomials. The target does not turn exclusion of a smaller range, a faster search, or a structural pruning rule into closure. Its `BOUNDED_COUNTEREXAMPLE` label is conservative and does not claim an exhaustive classification or a positive theorem outside the bounded input class.

The targeted tests confirmed the role equation, the separate length/sum bounds, rational canonicality, all 29 sample values, the degree ceiling, and the `t+1` regression for a base LR coefficient of 2. Those checks support the semantic mapping but are not a verifier red-team review.

No statement-fidelity correction is required. Future changes to the official prompt or its bounds must trigger the existing stop condition and a new review.

## Final-card recheck

Date: 2026-08-14. **PASS.** Final `target-card.json` raw-file SHA-256: `1ab87748125aa10d24229cadc47c8d04a99add70aeb42465b8be8232b458aad8`. Its `problem_card_sha256` value, `6d891e29afadbdc210962f87dc63add362ec2b1d5ee1a3de0886a70abef534c0`, matches a fresh canonical-hash computation of the corresponding `data/problems.json` entry. The final literature-baseline edit records known nonnegativity through partition length 4 and changes only partial-progress guidance; the bounded quantifiers, witness criterion, and `BOUNDED_COUNTEREXAMPLE` claim scope remain unchanged.
