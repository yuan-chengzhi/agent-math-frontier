# AIM #60 frozen-baseline improvement target

Status: **not active**. This directory intentionally has no
`target-bundle.json` and no baseline, review, red-team, or budget receipt.
Those records require separate, genuine review and cannot be inferred from the
presence of a checker or a reconstructed certificate.

The first-launch target is deliberately narrower than AIM Problem 60. It asks
for one positive integer `a < 10^20` whose first positive prime value
`x^12 + a` occurs at an `x` strictly larger than the frozen public example
`a = 488669`, `x = 616980`. It does **not** claim that this example is the
current world record, and it does not ask the verifier to prove global
optimality over all `a < 10^20`. The implementation caps the claimed first
prime index at 10,000,000 as an explicit initial resource boundary.

Every preceding positive `x` must have an exact compositeness witness. A
candidate may compress these witnesses with congruence rules: each listed
divisor and residue is checked against `r^12 + a`, and the verifier itself
enumerates the covered indices. All indices not covered in that way must occur
in canonical order with a non-trivial exact factor. This makes a sieve an
optimization only; it cannot silently omit an `x`.

The final value must carry an Atkin--Morain ECPP chain. The offline checker
independently checks the chain, Hasse and size bounds, curve nonsingularity,
elliptic-curve multiples, and the terminal 64-bit prime. No probable-prime
claim, CAS status flag, or search transcript is trusted.

The baseline evidence uses the observation recorded by OEIS A122131 only
after checking it: for `a = 488669`, every possible prime index must be a
multiple of `2*3*5*7*13 = 2730`. The verifier still checks all five modular
rules and exact factors for every remaining multiple; the number 2730 is not
hard-coded as an exemption.
