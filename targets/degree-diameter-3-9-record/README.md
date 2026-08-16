# Degree--diameter (3,9) active target

Status: **active as of 2026-08-14**. `target-bundle.json` binds the final card,
neutral baseline, two independent review-process records, verifier red team and
frozen experiment budget. Activation does not itself claim a new graph or grant
model-launch authority.

The candidate format is a strict JSON object with `schema`, `n`, and a
canonical undirected edge list. Every edge must be `[u,v]` with `u < v`.
The production dispatcher accepts exactly when both independent checkers agree
that:

- `601 <= n <= 1534`;
- the edge list describes a simple connected graph;
- the **maximum** degree is at most 3 (regularity is not required); and
- the all-pairs shortest-path diameter is at most 9.

The upper resource bound is the Moore bound for maximum degree 3 and diameter
9. The two implementations use queue-based all-pairs BFS and independent
bit-set wavefront expansion, respectively. The dispatcher snapshots the input
once, runs both implementations as isolated Python processes, and fails closed
on disagreement.

The 600-vertex source graph is deliberately not redistributed.  The outer
Mendeley V11 dataset is labelled CC BY 4.0, but the graph is attributed to
Geoffrey Exoo and no file-level grant resolving the dataset's third-party
content reservation was found.  `source-metadata.json` therefore retains only
the versioned DOI/URL, archive and member hashes, derived-output hash, measured
facts and the licensing caveat.  `convert_implicit.py` can deterministically
normalize exact source bytes supplied locally; ordinary tests use a
repository-authored synthetic cubic fixture.  The externally reproducible
baseline has order 600 and is not itself a production-success candidate.
