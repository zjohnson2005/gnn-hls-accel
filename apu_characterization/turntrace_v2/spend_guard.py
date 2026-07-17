"""Hard spend ceiling for collect_cloud --live (P2 pre-spend gate)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SpendCeilingExceeded(RuntimeError):
    """Raised when projected or running spend would exceed budget_lock hard ceiling."""


class SpendLockNotAuthorized(RuntimeError):
    """Raised when a campaign lock exists but is not authorized for live use."""


@dataclass
class BudgetLock:
    path: Path
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "BudgetLock":
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"budget_lock.json missing at {path}; refuse --live until Step 1 gate passes"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        _validate_filled(raw, path)
        return cls(path=path, raw=raw)

    @property
    def hard_ceiling_usd(self) -> float:
        return float(self.raw["totals"]["hard_ceiling_usd"])

    @property
    def projected_usd(self) -> float:
        return float(self.raw["totals"]["projected_usd"])

    def cell(self, cell_id: str) -> dict[str, Any]:
        for c in self.raw["cells"]:
            if c["cell_id"] == cell_id:
                return c
        raise KeyError(f"cell {cell_id} not in budget_lock")

    def assert_live_authorized(
        self,
        *,
        expected_campaign: str | None = None,
        payload_manifest_sha256: str | None = None,
    ) -> None:
        if not bool(self.raw.get("live_authorized")):
            raise SpendLockNotAuthorized(
                f"{self.path}: budget is locked but live_authorized is false"
            )
        if expected_campaign and self.raw.get("campaign") != expected_campaign:
            raise SpendLockNotAuthorized(
                f"{self.path}: campaign {self.raw.get('campaign')!r} does not match "
                f"{expected_campaign!r}"
            )
        if payload_manifest_sha256 is not None:
            observed = str(self.raw.get("payload_manifest_sha256") or "")
            if observed != payload_manifest_sha256:
                raise SpendLockNotAuthorized(
                    f"{self.path}: payload manifest hash mismatch"
                )

    def estimate_run_usd(
        self,
        *,
        cell_id: str,
        n_trajectories: int,
        harnesses: int,
        turns_per_traj: float,
        mean_tokens_in: float | None = None,
        mean_tokens_out: float | None = None,
        model_id: str | None = None,
    ) -> float:
        cell = self.cell(cell_id)
        te = self.raw["token_estimate"]
        tin = float(mean_tokens_in if mean_tokens_in is not None else te["mean_tokens_in_per_call"])
        tout = float(mean_tokens_out if mean_tokens_out is not None else te["mean_tokens_out_per_call"])
        # Price from cell rates; if smoke model differs, still use cell rates as upper bound
        # unless model_id matches smoke_model (then use same cell rates — OpenAI list).
        usd_in = float(cell["usd_per_1m_in"])
        usd_out = float(cell["usd_per_1m_out"])
        if model_id and model_id == cell.get("smoke_model_id") and cell_id == "C1":
            # gpt-4.1-mini published rates
            usd_in, usd_out = 0.4, 1.6
        calls = n_trajectories * harnesses * turns_per_traj
        return calls * tin / 1e6 * usd_in + calls * tout / 1e6 * usd_out

    def assert_under_ceiling(
        self,
        *,
        planned_usd: float,
        spent_usd: float = 0.0,
        allow_override: bool = False,
        label: str = "run",
    ) -> None:
        total = planned_usd + spent_usd
        ceiling = self.hard_ceiling_usd
        if total <= ceiling:
            return
        if allow_override:
            return
        raise SpendCeilingExceeded(
            f"{label}: projected+spent ${total:.4f} exceeds hard ceiling "
            f"${ceiling:.4f} from {self.path}. Pass --allow-spend-override to force "
            f"(logged manual override required)."
        )


def _validate_filled(raw: dict[str, Any], path: Path) -> None:
    cells = raw.get("cells") or []
    if len(cells) < 2:
        raise ValueError(f"{path}: need ≥2 cells")
    for c in cells:
        for key in ("model_id", "usd_per_1m_in", "usd_per_1m_out", "n_trajectories"):
            if key not in c:
                raise ValueError(f"{path}: cell missing {key}")
        if "FILL" in str(c["model_id"]).upper() or float(c["usd_per_1m_in"]) <= 0:
            raise ValueError(f"{path}: placeholder pricing/model still present in {c['cell_id']}")
    totals = raw.get("totals") or {}
    if float(totals.get("hard_ceiling_usd") or 0) <= 0:
        raise ValueError(f"{path}: hard_ceiling_usd must be > 0")
    if int(raw.get("n_derivation", {}).get("locked_N_per_cell") or 0) < 10:
        raise ValueError(f"{path}: locked_N_per_cell must be ≥10 (spec floor)")
