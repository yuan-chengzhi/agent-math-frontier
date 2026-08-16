# AIM #60 provisional-baseline experiment target

Status: **experimental, not audited active**. This directory intentionally has no
`target-bundle.json` and no baseline, review, red-team, or budget receipt.
Those records require separate, genuine review and cannot be inferred from the
presence of a checker or a reconstructed certificate.

The v2 experiment is deliberately narrower than AIM Problem 60. It asks for
one positive integer `a < 10^20` whose first positive prime value `x^12 + a`
occurs at `x >= 1455091`. The threshold is one above the strongest same-form
public report found in the 2026-08-14 search: `a = 26060579`, `x = 1455090`.
That page is prior-art evidence, not an independently certified maintained
record. The implementation caps the claimed first-prime index at 10,000,000.

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

The retained v1 baseline evidence uses the observation recorded by OEIS A122131 only
after checking it: for `a = 488669`, every possible prime index must be a
multiple of `2*3*5*7*13 = 2730`. The verifier still checks all five modular
rules and exact factors for every remaining multiple; the number 2730 is not
hard-coded as an exemption.

`amf.aim60.certificate.v1` and `candidate.schema.json` remain immutable
regression artifacts for the old 616980 threshold. The experimental portfolio
selects `amf.aim60.certificate.v2` and `candidate.v2.schema.json`; both reuse the
audited v1 mathematical kernel while enforcing the provisional 1455091 floor.
