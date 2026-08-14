#!/usr/bin/env python3
"""Regenerate raw metadata indexes from pinned upstream repositories.

The raw layer intentionally omits full mathematical statements. It is a lead
index, not the curated or active queue.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import ssl
import sys
import tarfile
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import certifi
    import yaml
except ImportError:  # pragma: no cover - exercised by a clean checkout
    print("Sync dependencies are missing: python3 -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "data" / "upstream"
ERDOS_REPO = "teorth/erdosproblems"
FORMAL_REPO = "google-deepmind/formal-conjectures"
DECL_RE = re.compile(r"^\s*(?:(?:noncomputable|private|protected)\s+)*(?:theorem|lemma|def)\s+([^\s:(\[{]+)")


def request_bytes(url: str) -> bytes:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "agent-math-frontier-sync/1"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(Request(url, headers=headers), timeout=90, context=context) as response:
            return response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def github_revision(repo: str, ref: str) -> str:
    payload = request_bytes(f"https://api.github.com/repos/{repo}/commits/{quote(ref, safe='')}")
    return json.loads(payload)["sha"]


def read_erdos_remote(revision: str) -> bytes:
    return request_bytes(f"https://raw.githubusercontent.com/{ERDOS_REPO}/{revision}/data/problems.yaml")


def formal_files_remote(revision: str):
    payload = request_bytes(f"https://api.github.com/repos/{FORMAL_REPO}/tarball/{revision}")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            marker = "/FormalConjectures/"
            if not member.isfile() or marker not in member.name or not member.name.endswith(".lean"):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            relative = "FormalConjectures/" + member.name.split(marker, 1)[1]
            yield relative, handle.read().decode("utf-8")


def formal_files_local(root: Path):
    base = root / "FormalConjectures"
    if not base.is_dir():
        raise RuntimeError(f"{root} does not contain FormalConjectures/")
    for path in sorted(base.rglob("*.lean")):
        yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")


def parse_formal_open(files, revision: str, retrieved_at: str) -> dict:
    declarations: list[dict] = []
    file_count = 0
    for path, text in files:
        file_count += 1
        awaiting = False
        attribute_line = 0
        for line_number, line in enumerate(text.splitlines(), start=1):
            compact = " ".join(line.replace("@[", "").replace("]", "").split())
            if "category research open" in compact:
                awaiting = True
                attribute_line = line_number
            if not awaiting:
                continue
            match = DECL_RE.match(line)
            if match:
                declaration = match.group(1)
                declarations.append(
                    {
                        "path": path,
                        "declaration": declaration,
                        "attribute_line": attribute_line,
                        "declaration_line": line_number,
                        "artifact_url": f"https://github.com/{FORMAL_REPO}/blob/{revision}/{path}#L{line_number}",
                    }
                )
                awaiting = False
            elif line_number - attribute_line > 12:
                raise RuntimeError(f"could not find declaration after open tag at {path}:{attribute_line}")
    declarations.sort(key=lambda item: (item["path"], item["declaration_line"], item["declaration"]))
    return {
        "schema_version": 1,
        "source": f"https://github.com/{FORMAL_REPO}",
        "upstream_revision": revision,
        "retrieved_at": retrieved_at,
        "semantic_warning": "A research/open tag is not proof that the translation is faithful or that the source problem remains open.",
        "lean_file_count": file_count,
        "declaration_count": len(declarations),
        "declarations": declarations,
    }


def parse_erdos(raw: bytes, revision: str, retrieved_at: str) -> dict:
    records = yaml.safe_load(raw)
    if not isinstance(records, list):
        raise RuntimeError("unexpected Erdős YAML root")
    keep = [
        "number",
        "prize",
        "informal_status",
        "formal_status",
        "status",
        "formalized",
        "tags",
        "oeis",
    ]
    problems = []
    for record in records:
        item = {key: record[key] for key in keep if key in record}
        item["problem_url"] = f"https://www.erdosproblems.com/{record['number']}"
        problems.append(item)
    problems.sort(key=lambda item: int(item["number"]))
    return {
        "schema_version": 1,
        "source": f"https://github.com/{ERDOS_REPO}",
        "upstream_revision": revision,
        "retrieved_at": retrieved_at,
        "semantic_warning": "Source status is a lead. Recheck the intended statement, literature and current status before promotion.",
        "problem_count": len(problems),
        "problems": problems,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def retrieval_date(path: Path, revision: str, requested: str | None) -> str:
    if requested:
        return requested
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("upstream_revision") == revision and previous.get("retrieved_at"):
                return previous["retrieved_at"]
        except (OSError, json.JSONDecodeError):
            pass
    return date.today().isoformat()


def git_head(path: Path) -> str:
    head = path / ".git" / "HEAD"
    if not head.exists():
        raise RuntimeError(f"{path} has no readable git revision; pass --*-revision")
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref_path = path / ".git" / value.removeprefix("ref: ")
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
        packed = path / ".git" / "packed-refs"
        if packed.exists():
            suffix = value.removeprefix("ref: ")
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line and not line.startswith("#") and line.endswith(f" {suffix}"):
                    return line.split(" ", 1)[0]
        raise RuntimeError(f"cannot resolve {value} in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--erdos-ref", default="main")
    parser.add_argument("--formal-ref", default="main")
    parser.add_argument("--erdos-dir", type=Path, help="use an existing checkout instead of the network")
    parser.add_argument("--formal-dir", type=Path, help="use an existing checkout instead of the network")
    parser.add_argument("--erdos-revision")
    parser.add_argument("--formal-revision")
    parser.add_argument("--retrieved-at", help="override both retrieval dates (mainly for reproducible tests)")
    args = parser.parse_args()

    try:
        if args.erdos_dir:
            erdos_revision = args.erdos_revision or git_head(args.erdos_dir)
            erdos_raw = (args.erdos_dir / "data" / "problems.yaml").read_bytes()
        else:
            erdos_revision = args.erdos_revision or github_revision(ERDOS_REPO, args.erdos_ref)
            erdos_raw = read_erdos_remote(erdos_revision)

        if args.formal_dir:
            formal_revision = args.formal_revision or git_head(args.formal_dir)
            formal_files = formal_files_local(args.formal_dir)
        else:
            formal_revision = args.formal_revision or github_revision(FORMAL_REPO, args.formal_ref)
            formal_files = formal_files_remote(formal_revision)

        erdos_path = UPSTREAM / "erdos-problems.json"
        formal_path = UPSTREAM / "formal-conjectures-open.json"
        erdos_date = retrieval_date(erdos_path, erdos_revision, args.retrieved_at)
        formal_date = retrieval_date(formal_path, formal_revision, args.retrieved_at)
        erdos = parse_erdos(erdos_raw, erdos_revision, erdos_date)
        formal = parse_formal_open(formal_files, formal_revision, formal_date)
        write_json(erdos_path, erdos)
        write_json(formal_path, formal)
        print(
            f"indexed {erdos['problem_count']} Erdős records and "
            f"{formal['declaration_count']} open Formal Conjectures declarations"
        )
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
