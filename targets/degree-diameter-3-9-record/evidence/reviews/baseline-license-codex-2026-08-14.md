# Licensing and provenance audit: DD(3,9) `Exoo_600`

Date checked: 2026-08-14

Verdict: **CONDITIONAL** for public redistribution of both the raw adjacency list and the complete normalized edge list. The versioned Mendeley dataset carries CC BY 4.0 and contains the exact bytes now in the repository, which is strong affirmative evidence. However, the same dataset identifies the graph as Geoffrey Exoo's work, while Mendeley's licence notice expressly warns that content identified as belonging to a third party may require further permission. I found no file-level licence or explicit permission from Exoo resolving that reservation. This is a conservative provenance assessment, not legal advice.

## Sources checked

- Current maintainer table: <https://web.mat.upc.edu/francesc.comellas/delta-d/taula_delta_d.html>
- Current diameter-9 description: <https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g9.html>
- Current raw-file URL: <https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/adjacencies/adjD9/Exoo_600.txt>
- Versioned dataset landing page: <https://data.mendeley.com/datasets/d75dzbjd4k/11>
- Version DOI: <https://doi.org/10.17632/d75dzbjd4k.11>
- Mendeley version-comparison page: <https://data.mendeley.com/datasets/compare/d75dzbjd4k>
- Mendeley public file metadata endpoint: <https://data.mendeley.com/public-api/datasets/d75dzbjd4k/files?folder_id=root&version=11>
- Associated primary paper: <https://arxiv.org/abs/2406.18994>
- CC BY 4.0 deed and legal code: <https://creativecommons.org/licenses/by/4.0/> and <https://creativecommons.org/licenses/by/4.0/legalcode.en>

## Provenance and byte identity

Mendeley Data Version 11 is titled *Table of Large Degree/Diameter Graphs*, names Francesc Comellas as contributor, was published on 2026-01-28, and displays `Creative Commons Attribution 4.0 International` as its licence. Its description says that the package contains the table and adjacency lists for most graphs below 20,000 vertices.

The public file endpoint reports one archive:

```text
filename: delta-d@260127.zip
file id: f3887e12-e959-4c50-b0b1-071638c1a70a
bytes: 120599994
SHA-256: aafc66b97eba2c007ef53145bb7a2c0bb413d2d0faeacfaa4d69d44bcc00bf14
```

The archive SHA-256 above is repository metadata reported by Mendeley; I did not independently download and hash all 120 MB. I did independently retrieve and parse the version-pinned ZIP central directory and the compressed member at its recorded local-header offset. Version 11 contains

```text
delta-d/desc_g/adjacencies/adjD9/Exoo_600.txt
compression: deflate
compressed bytes: 3619
uncompressed bytes: 13201
CRC-32: 98cd53e6
```

The independently decompressed member has SHA-256

```text
12de7e2c303955f57196888a0eecae17d7e872616a638d6f7772b09f77f34106
```

and is byte-for-byte identical to both the maintainer-hosted current file and the repository's `evidence/baseline/Exoo_600.txt`. Thus this is not merely a similarly named graph: the public repository copy is the exact member of the CC-licensed V11 package.

The repository's deterministic conversion produces an 8,727-byte canonical edge-list file with SHA-256

```text
efa7763007d3f1771c547d47b1ab8280ecf8f42b854850bc3e814a26b47ef5ae
```

and the reproduced factual metrics are `n=600`, 900 edges, maximum degree 3, connected, diameter 9.

## What the licence establishes

The V11 landing page applies CC BY 4.0 to the dataset version. CC BY 4.0 permits copying, redistribution, transformation, and building upon licensed material, including commercially, provided appropriate credit is given, the licence is linked, modifications are indicated, and no endorsement is implied. Version 4.0 also addresses applicable sui-generis database rights.

Mendeley's embedded licence description is materially narrower than an unconditional ownership warranty. It says that the dataset may be shared and modified with attribution, but also says that further permission may be required for content identified as belonging to a third party. The CC legal code likewise grants only rights the licensor has authority to license and gives no warranty of title or non-infringement.

That reservation matters here. The maintainer table and associated paper identify `Exoo` graphs as graphs built by Geoffrey Exoo, cite his work, and describe the relevant records as personal communications. Version 11 contains no path whose name indicates `LICENSE`, `LICENCE`, `COPYING`, `COPYRIGHT`, `RIGHTS`, `NOTICE`, `README`, `CITATION`, or `AUTHORS`; in particular, I found no member-level grant or exclusion for `Exoo_600.txt`. Public download availability alone is not redistribution permission.

It is plausible that Comellas intentionally licensed the whole archive, including this file, and graph adjacency facts may receive little or no copyright protection in some jurisdictions. Neither proposition should be silently promoted into a worldwide rights conclusion. The complete 600-vertex adjacency relation and a complete normalized re-encoding should be treated alike for this audit: normalization changes syntax but carries the whole graph, so it is not a safe way to evade an unresolved source-rights question.

Hashes, byte counts, graph order, edge count, degree, diameter, source URLs, and the fact that two byte strings agree are factual metadata. Recording those facts is distinct from redistributing the 13,201-byte adjacency list itself. The repository-authored conversion/checking code also need not embed the source data.

## Safest reproducibility design while permission is unresolved

Do not publish either `Exoo_600.txt` or `Exoo_600.normalized.json` in the public repository yet. Preserve reproducibility with:

1. A small provenance manifest containing the V11 DOI, landing-page URL, archive filename/id/reported size/reported SHA-256, internal member path, member size/CRC/SHA-256, direct maintainer URL, conversion-script hash, normalized-output hash, and reproduced graph metrics.
2. Repository-owned fetch/verify/convert code that downloads the source on demand, requires the exact pinned hashes, and derives the normalized edge list locally. Prefer V11 as the licence/provenance anchor; the smaller maintainer URL may be used as a byte-identical transport mirror only after its hash is checked.
3. Synthetic, repository-owned graph fixtures for ordinary offline unit tests of parsing, normalization, BFS, bit-set checking, disagreement, and failure behavior. A baseline integration test should run only when the externally fetched/cached artifact is explicitly supplied; absence of that artifact must not fail normal CI.
4. Factual baseline metadata in the target card and research prompt, clearly labelled as externally reproducible evidence rather than bundled data.

This design retains exact reproducibility without making public redistribution of the disputed bytes a prerequisite for the verifier or campaign.

## How to clear the condition

The cleanest resolution is a written statement from Francesc Comellas, preferably also acknowledged by Geoffrey Exoo, that CC BY 4.0 for DOI `10.17632/d75dzbjd4k.11` covers the specific member `delta-d/desc_g/adjacencies/adjD9/Exoo_600.txt` and permits redistribution and normalization. An explicit file-level licence added by the rights holder would also suffice. Preserve the permission text, date, sender identity/provenance, and hash as evidence; do not infer it from silence.

If that condition is cleared, redistribution should include at least:

- attribution to *Table of Large Degree/Diameter Graphs*, Francesc Comellas, Version 11, DOI `10.17632/d75dzbjd4k.11`;
- identification of Geoffrey Exoo as the graph constructor;
- a link to CC BY 4.0 and the source member/URL;
- an explicit notice that the normalized JSON is a deterministic format conversion and that no endorsement is implied.

Until then, the current files are useful locally for audit, but they should not be included in a public commit solely on the basis of downloadability or the dataset-level badge.
