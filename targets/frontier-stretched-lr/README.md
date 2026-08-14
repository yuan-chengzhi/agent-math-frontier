# Stretched Littlewood--Richardson target implementation

This directory is the **active 2026-08-14 target package** for
`frontier-stretched-lr`. `target-bundle.json` binds the exact card, neutral
baseline, independent statement/open-status reviews, verifier red team and
frozen experiment budget. Activation does not assert that a counterexample
exists and does not grant model-launch authority.

## Frozen convention and finite certificate

The outer partition is `lambda` and the two inner partitions are `mu` and
`nu`:

```text
P(t) = c^(t*lambda)_(t*mu,t*nu),    |lambda| = |mu| + |nu|.
```

Every partition is encoded canonically as a nonempty weakly decreasing list
of positive integers.  Each list has length at most 7 and sum at most 30.
These are the bounds in the Epoch AI prompt checked on 2026-08-14; the linked
background PDF discusses a broader search and must not be used to silently
relax the frozen prompt.

The background PDF states the safe degree bound

```text
deg P <= binomial(length(lambda) + 1, 2) <= 28.
```

Consequently the exact values at the 29 positive integers `t = 1,...,29`
uniquely determine `P`.  A candidate supplies all 29 values and the complete
monomial-basis polynomial, constant coefficient first.  Rational coefficients
are represented by reduced numerator/positive-denominator pairs; the source
does not justify assuming that every monomial coefficient is integral.  A
candidate is successful only when a declared coefficient is negative and both
independent implementations reproduce the entire polynomial.

Accordingly, the inherited semantic mode name
`exact_integer_polynomial_two_implementations` is read as “the polynomial is
recovered from exact integer LR evaluations by two implementations,” not as an
extra assertion that all power-basis coefficients lie in the integers.

## Independent exact paths

The primary checker counts Littlewood--Richardson tableaux directly.  It
processes the skew diagram row by row, enforcing semistandard columns and the
lattice-word prefix inequalities.

The secondary checker does not enumerate LR tableaux.  It expands `s_nu` by
the Jacobi--Trudi determinant and obtains the target Schur coefficient by
signed, memoized chains of horizontal strips under the Pieri rule.  It also
recovers the power-basis polynomial with an exact rational Vandermonde solve,
whereas the primary checker uses finite differences in the Newton basis.

Both implementations are pure Python, offline, operation-bounded and run in
separate isolated subprocesses.  A timeout, arithmetic-size limit, checker
failure or disagreement is an infrastructure failure, never an accepted
mathematical result.

## Current route baseline

Ferudun, arXiv:2607.22301v1, proves coefficientwise nonnegativity when all
three partitions have length at most four.  That public theorem is part of the
frozen baseline: a search life should begin with maximum partition length at
least five, and a finite exclusion wholly inside the length-four range is a
reproduction rather than new partial progress.  The theorem does not close the
Epoch bounds, which permit lengths five through seven.

## Primary-source binding and regression cases

- Prompt page: <https://epoch.ai/frontiermath/open-problems/stretched-lr-coefficients>
- Background PDF: <https://epoch.ai/files/open-problems/stretched-lr-coefficients.pdf>
- PDF SHA-256 as retrieved 2026-08-14:
  `135f583c5d6edacf1251624f5f0aaad1b85190bab5a7703173b1ba84e36d8052`

`evidence/regression/cases.json` contains small mathematical regressions, not
a claimed counterexample.  In particular,

```text
c^(t*(3,2,1))_(t*(2,1),t*(2,1)) = t + 1.
```

At `t=1` its LR coefficient is 2; the source PDF records the theorem that an
LR coefficient equal to 2 stretches to `t+1`.  The direct tableau and
Jacobi--Trudi/Pieri implementations additionally reproduce all 29 listed
values.  The other cases exercise a Pieri coefficient identically equal to 1
and a column obstruction identically equal to 0.
