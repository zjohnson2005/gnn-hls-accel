"""INF-6: resolve which pre-registered prediction block belongs in plan.json."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAP3_PREDICTIONS_PATH = ROOT / "derived" / "cap3" / "CAP3_PREDICTIONS.json"


def _norm_spec(path: Path, *, repo_root: Path) -> Path:
    p = path if path.is_absolute() else (repo_root / path)
    try:
        return p.resolve()
    except OSError:
        return p


def match_cap3_arm(
    *,
    model_spec: Path,
    repo_root: Path | None = None,
    predictions_path: Path | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """Return (arm_key, arm_block, file_doc) if model_spec matches a CAP-3 arm."""
    root = repo_root or ROOT
    path = predictions_path or (root / "derived" / "cap3" / "CAP3_PREDICTIONS.json")
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    want = _norm_spec(model_spec, repo_root=root)
    want_name = want.name
    for arm_key, arm in (doc.get("arms") or {}).items():
        arm_spec = Path(str(arm.get("model_spec") or ""))
        if not arm_spec.parts:
            continue
        cand = _norm_spec(arm_spec, repo_root=root)
        if cand == want or cand.name == want_name:
            return str(arm_key), arm, doc
    return None


def resolve_ttft_slo_plan_predictions(
    *,
    model_spec: Path,
    arm_ids: list[str],
    slo_s: float,
    repeats: int,
    default_c2_predictions: Callable[..., dict[str, Any]],
    repo_root: Path | None = None,
    predictions_path: Path | None = None,
) -> dict[str, Any]:
    """Pick CAP-3 arm predictions (pointer) or the default C-2 AM-038 block.

    When ``model_spec`` matches ``derived/cap3/CAP3_PREDICTIONS.json``, the plan
    carries a pointer at that file plus the arm's prediction block — not the
    stale C-2 "three turn-1 limits agree within 250 tokens" claim.
    """
    matched = match_cap3_arm(
        model_spec=model_spec,
        repo_root=repo_root,
        predictions_path=predictions_path,
    )
    if matched is not None:
        arm_key, arm, doc = matched
        rel = "derived/cap3/CAP3_PREDICTIONS.json"
        if predictions_path is not None and repo_root is not None:
            try:
                rel = str(predictions_path.resolve().relative_to(repo_root.resolve())).replace(
                    "\\", "/"
                )
            except ValueError:
                rel = str(predictions_path).replace("\\", "/")
        return {
            "source": "cap3_predictions_file",
            "predictions_path": rel,
            "arm_key": arm_key,
            "model_spec": arm.get("model_spec"),
            "registered_utc": doc.get("registered_utc"),
            "experiment": doc.get("experiment"),
            "predictions": arm.get("predictions"),
            "search": arm.get("search"),
            "note": (
                "CAP-3 arm predictions apply for this -ModelSpec. "
                "C-2 three-arm KV agreement claim (AM-038) does not apply to a "
                "single-arm capability run."
            ),
            "c2_am038_not_applicable": True,
        }

    inline = default_c2_predictions(slo_s=slo_s, repeats=repeats)
    return {
        "source": "c2_am038_inline",
        "predictions_path": None,
        "arm_key": None,
        "arms": list(arm_ids),
        "note": (
            "Default C-2 / AM-038 turn-1 KV agreement prediction "
            "(three limits agree within resolution)."
        ),
        "c2_am038_not_applicable": False,
        **inline,
    }
