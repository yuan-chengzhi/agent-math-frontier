# Frozen experiment and active targets

Every machine-addressable experiment has at least `target-card.json` and
`candidate.schema.json`, and selects a registered versioned verifier. These
minimal packages feed `data/experimental-portfolio.json`; they are runnable,
but do not imply completed novelty, fidelity, or red-team review.

An audited active promotion additionally has this shape:

```text
targets/<problem-id>/
├── target-bundle.json
├── target-card.json
├── candidate.schema.json
└── evidence/
    ├── baseline/
    ├── red-team/
    ├── receipts/
    │   ├── baseline-*.json
    │   ├── review-*.json
    │   ├── red-team-*.json
    │   └── budget-*.json
    └── reviews/
        └── process/
```

The names other than `target-bundle.json` are conventional; the bundle's exact
raw-byte bindings are authoritative. Receipts are compiled only from existing
host-observed process evidence by `scripts/prepare_activation.py`; placeholders
are rejected. See
[`CONTRIBUTING.md`](../CONTRIBUTING.md) and the V1 schemas in [`schemas/`](../schemas/).

Each review receipt binds the complete report, the target source revision, an
auditable reviewer-authority record, and session evidence. These bindings make
later tampering visible; they are not authentication, a cryptographic
signature, or proof that the mathematical judgment is correct.

Use `python scripts/verify_candidate.py --list` to list all runnable targets,
then `python scripts/verify_candidate.py <problem-id> <candidate.json>` to run
the manifest-selected verifier. Exit 0 is mathematical acceptance under the
frozen target card, exit 1 is candidate rejection, and exit 2 is an apparatus
or invocation failure.
