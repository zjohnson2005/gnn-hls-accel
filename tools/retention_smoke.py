"""CPU smoke for the retention prompt builder. No measurement, no device.

Refuses any fixture whose name contains PREREG or AMENDMENT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.retention_prompt import build_cell  # noqa: E402


def _refuse_prereg(path: Path) -> None:
    name = path.name.upper()
    if "PREREG" in name or "AMENDMENT" in name:
        raise SystemExit("REFUSED -- runner does not read prereg or amendment files")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--fixture":
        raise SystemExit("usage: retention_smoke.py --fixture PATH")
    path = Path(args[1])
    _refuse_prereg(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = build_cell(
        source=str(doc["source"]),
        spans=[(int(pair[0]), int(pair[1])) for pair in doc["required_spans"]],
        positional_budget_tokens=int(doc["positional_budget_tokens"]),
        observations=[str(item) for item in doc["observations"]],
        obs_mask_k=int(doc["obs_mask_k"]),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
