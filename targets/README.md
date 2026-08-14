# Frozen active targets

This directory contains the frozen packages behind the active portfolio. An
active promotion has this shape:

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
