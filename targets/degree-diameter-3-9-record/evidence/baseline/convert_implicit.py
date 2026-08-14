#!/usr/bin/env python3
"""Deterministically normalize the maintainer's implicit adjacency list."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile


ORDER = 600
DEGREE = 3
MAXIMUM_SOURCE_BYTES = 65_536
OUTPUT_SCHEMA = "AMF_DD39_BASELINE_GRAPH_1"


def read_source(path: Path) -> bytes:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("source must be a regular non-symlink file")
    if metadata.st_size > MAXIMUM_SOURCE_BYTES:
        raise ValueError("source exceeds the conversion bound")
    raw = path.read_bytes()
    if len(raw) != metadata.st_size:
        raise ValueError("source changed while being read")
    return raw


def convert(raw: bytes) -> dict[str, object]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeError as exc:
        raise ValueError("source is not ASCII") from exc
    rows = text.splitlines()
    while rows and not rows[-1].strip():
        rows.pop()
    if len(rows) != ORDER or any(not row.strip() for row in rows):
        raise ValueError("source must contain exactly 600 nonempty adjacency rows")

    adjacency: list[set[int]] = []
    for vertex, row in enumerate(rows):
        tokens = row.split()
        if len(tokens) != DEGREE:
            raise ValueError(f"row {vertex} must contain exactly three neighbors")
        neighbors: set[int] = set()
        for token in tokens:
            if not token.isascii() or not token.isdecimal():
                raise ValueError(f"row {vertex} contains a non-decimal vertex")
            neighbor = int(token, 10)
            if not 0 <= neighbor < ORDER:
                raise ValueError(f"row {vertex} contains an out-of-range vertex")
            if neighbor == vertex:
                raise ValueError(f"row {vertex} contains a self-loop")
            neighbors.add(neighbor)
        if len(neighbors) != DEGREE:
            raise ValueError(f"row {vertex} repeats a neighbor")
        adjacency.append(neighbors)

    for vertex, neighbors in enumerate(adjacency):
        for neighbor in neighbors:
            if vertex not in adjacency[neighbor]:
                raise ValueError("implicit adjacency relation is not symmetric")

    edges = sorted(
        [vertex, neighbor]
        for vertex, neighbors in enumerate(adjacency)
        for neighbor in neighbors
        if vertex < neighbor
    )
    if len(edges) != ORDER * DEGREE // 2:
        raise ValueError("unexpected edge count")
    return {"edges": edges, "n": ORDER, "schema": OUTPUT_SCHEMA}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    atomic_write(arguments.output, canonical_bytes(convert(read_source(arguments.source))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
