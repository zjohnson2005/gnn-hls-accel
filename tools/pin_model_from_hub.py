"""Pin a pre-converted OpenVINO IR from Hub metadata, before it is downloaded (Task BE).

Writes a FetchedModelSpec YAML with the same fields and the same ir_sha256 roll-up as
seam.tools.fetch_model, without transferring the large files:
- LFS files (weights, tokenizer binaries): sha256 = the Hub's lfs.oid;
- non-LFS files: downloaded (small) and hashed here, and checked against the Hub git blob sha1.
The host download (seam.tools.fetch_model, verify against the Hub) must then produce the same
ir_sha256; the download scripts refuse a mismatch. download_method records that the pin came
from metadata. Only the Hub is contacted; nothing is written in models/.

  python tools/pin_model_from_hub.py --repo OpenVINO/Qwen3-8B-int8-ov --revision <sha> \\
      --ladder-position slice-8b --out configs/models/Qwen3-8B-int8-ov.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.tools.fetch_model import (  # noqa: E402
    _HF_API,
    FetchedModelSpec,
    _curl_json,
    _publisher_quantization,
    _remote_files,
)


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def build(repo: str, revision: str, ladder: str) -> FetchedModelSpec:
    info = _curl_json(f"{_HF_API}/{repo}/revision/{revision}")
    resolved = str(info.get("sha") or revision)
    if resolved != revision:
        raise SystemExit(f"REFUSED -- revision {revision} resolved to {resolved}; pin a full sha")
    names = sorted(str(e["rfilename"]) for e in info["siblings"])
    remote = _remote_files(repo, resolved)
    per_file: dict[str, str] = {}
    verification: dict[str, dict[str, object]] = {}
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        for name in names:
            rf = remote[name]
            total += int(rf.size)
            if rf.sha256:
                per_file[name] = rf.sha256
                verification[name] = {
                    "method": "sha256 (Hub lfs.oid; pinned before download)",
                    "expected_size": rf.size,
                    "expected_hash": rf.sha256,
                    "ok": True,
                }
                continue
            url = f"https://huggingface.co/{repo}/resolve/{resolved}/{name}"
            dst = tdir / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["curl", "-sSL", "--retry", "5", "--retry-all-errors", "-o", str(dst), url],
                check=True,
            )
            data = dst.read_bytes()
            blob = git_blob_sha1(data)
            if blob != rf.git_blob_sha1 or len(data) != rf.size:
                raise SystemExit(f"REFUSED -- {name}: blob {blob} size {len(data)} != Hub")
            per_file[name] = hashlib.sha256(data).hexdigest()
            verification[name] = {
                "method": "git-blob-sha1",
                "expected_size": rf.size,
                "actual_size": len(data),
                "expected_hash": rf.git_blob_sha1,
                "actual_hash": blob,
                "ok": True,
            }
        quant = _publisher_quantization(tdir)
    aggregate = hashlib.sha256(
        "\n".join(f"{n}:{d}" for n, d in sorted(per_file.items())).encode("utf-8")
    ).hexdigest()
    slug = repo.split("/")[-1]
    return FetchedModelSpec(
        name=slug,
        revision=resolved,
        ladder_position=ladder,
        source="pre-converted",
        source_repo=repo,
        download_method=(
            "pinned from Hub metadata on the Mac (tools/pin_model_from_hub.py); host download "
            "by seam.tools.fetch_model (curl, resumable) must reproduce ir_sha256"
        ),
        self_converted=False,
        publisher_quantization=quant,
        ir_dir=f"models/{slug}",
        ir_sha256=aggregate,
        ir_files=per_file,
        ir_bytes=total,
        fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        fetch_duration_s=0.0,
        transfer_attempts=dict.fromkeys(names, 0),
        verification=verification,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--ladder-position", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    spec = build(a.repo, a.revision, a.ladder_position)
    a.out.write_text(yaml.safe_dump(asdict(spec), sort_keys=False), encoding="utf-8")
    print(a.out, spec.ir_sha256, spec.ir_bytes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
