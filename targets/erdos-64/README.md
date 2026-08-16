# Erdős #64 active target package

Status: **active as of 2026-08-14**. `target-bundle.json` binds the final card,
neutral frontier brief, independent statement/open-status reviews, verifier red
team and frozen experiment budget. Activation is not evidence for a
counterexample and does not grant model-launch authority.

This package freezes a safe machine-checkable disproof route without directing
research lives to use that route. Agents may instead develop natural-language
structure theory, critique the known programs, run finite computations, search
for constructions, or formalize reusable Lean lemmas.

## Exact mathematical target

The conjecture asks whether every finite simple undirected graph of minimum
degree at least three contains a simple cycle of length `2^k` for some integer
`k >= 2`. The statement snapshot is pinned to Formal Conjectures revision
`b33d8678a28118c95d8d4f60b11faaf39ccff1e6` and declaration
`Erdos64.erdos_64`.

The V1 candidate is one explicit graph with `4 <= n <= 64`, represented by a
canonical edge list. Connectivity is deliberately not required: a disconnected
graph satisfying the hypotheses and avoiding every relevant cycle would still
refute the universal statement. If the exact verifier accepts such a graph,
that graph is a full counterexample to the global conjecture. The order cap only
limits what this implementation can consume; failure to find or accept a graph
in that range proves nothing beyond the inspected candidate.

## Exact checker and its resource ceiling

`amf.erdos64.counterexample.v1` rejects loops, duplicate or reverse-oriented
edges, out-of-range vertices, extra fields, and non-integer JSON. It checks the
minimum degree directly and then performs exhaustive simple-path searches for
cycle lengths `4, 8, 16, 32, 64` up to `n`. Each search fixes the least vertex
and one orientation, eliminating duplicates without omitting a cycle.

Exact fixed-length cycle detection is exponential in the worst case. The
checker therefore has both an input/order cap and a deterministic search-step
cap. Exhausting that cap exits as an apparatus error (`SEARCH_STEP_LIMIT`), not
as mathematical rejection. Thus the verifier is sound but intentionally
incomplete: it never accepts until all relevant searches finish, and it does
not pretend every valid graph in the representation bound is cheap to verify.

## Baselines that must not be rediscovered

The frozen source metadata records four existing programs that a research life
should read before claiming novelty:

- the conjecture is already established for `P_13`-free graphs;
- a minimum-order-and-size counterexample is known to have strong degree-three
  structure, including the `4/7` lower bound for cubic vertices;
- the pinned finite SAT/SMS project reports exclusion through 31 vertices.
- certified exhaustive computation excludes cubic bipartite counterexamples
  through 58 vertices.

These are route baselines, not review receipts. A larger finite nonexistence
search, another subclass theorem, or a formalized structural lemma is valuable
partial progress but does not close the root problem.

## Why V1 does not accept Lean roots

The upstream theorem skeleton contains both `answer(sorry)` and a `sorry` proof.
This repository currently lacks a content-pinned, offline Formal Conjectures and
Mathlib build closure plus a safe proof-body interface that excludes imported
sorried theorems, user axioms, and other trust escapes. Compiling an arbitrary
submitted Lean file would therefore overstate authority. Natural-language and
Lean positive or negative root proofs remain valid research outputs, but they
require a later dedicated checker and independent review before machine closure.

The active executable closure route remains counterexample-only. Natural or
Lean positive proofs are first-class research outputs, but require a separately
designed trust boundary before any formal closure claim.
