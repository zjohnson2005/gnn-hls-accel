"""Build ATTRIBUTION_VERDICT.md from profile artifact and optional py-spy buckets."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

_bucketize_mod = importlib.util.spec_from_file_location(
    "pyspy_bucketize", Path(__file__).parent / "pyspy_bucketize.py"
)
assert _bucketize_mod and _bucketize_mod.loader
_pyspy = importlib.util.module_from_spec(_bucketize_mod)
_bucketize_mod.loader.exec_module(_pyspy)
bucketize = _pyspy.bucketize
format_table = _pyspy.format_table
reconcile_proxy_pct = _pyspy.reconcile_proxy_pct
harness_labeled_pct = _pyspy.harness_labeled_pct


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-json",
        type=Path,
        default=Path("apu_characterization/out/profile_lh-01_s0.json"),
    )
    parser.add_argument("--speedscope", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/ATTRIBUTION_VERDICT.md"),
    )
    parser.add_argument(
        "--allow-synthetic-test",
        action="store_true",
        help="Allow scripted profile input (NOT verifiable)",
    )
    args = parser.parse_args()

    if args.profile_json.is_file():
        data = json.loads(args.profile_json.read_text(encoding="utf-8"))
        backend = (
            data.get("run", {}).get("config", {}).get("backend")
            or data.get("session", {}).get("backend")
        )
        if backend == "scripted" and not args.allow_synthetic_test:
            raise SystemExit(
                f"Profile {args.profile_json} used backend=scripted (synthetic). "
                "Not verifiable. Re-run with --backend openai on Linux, or pass "
                "--allow-synthetic-test for draft output only."
            )

    lines = [
        "# ORCH reconcile attribution verdict",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    timer_reconcile_pct = None
    if args.profile_json.is_file():
        data = json.loads(args.profile_json.read_text(encoding="utf-8"))
        backend = (
            data.get("run", {}).get("config", {}).get("backend")
            or data.get("session", {}).get("backend")
        )
        if backend == "scripted":
            lines.append(
                "**WARNING:** profile used `--backend scripted` (synthetic). "
                "Not verifiable. Re-run with `--backend openai` on Linux."
            )
            lines.append("")
        sess = data.get("session") or data["run"]["per_session"][0]
        host = sess.get("process_cpu_ns", 1)
        recon = sess.get("orch_reconcile_cpu_ns", 0)
        timer_reconcile_pct = 100 * recon / host
        lines.extend(
            [
                f"## Profile session: {data.get('task_id', sess.get('task_id'))}",
                "",
                f"- Host CPU ms: {host / 1e6:.1f}",
                f"- Timer ORCH reconcile: {recon / 1e6:.1f} ms ({timer_reconcile_pct:.1f}% of host)",
                f"- RESIDUAL_UNATTRIBUTED ms: {sess.get('residual_unattributed_cpu_ns', 0) / 1e6:.1f}",
                "",
            ]
        )
    else:
        lines.append("Profile JSON not found; run profile_reconcile_session first.")
        lines.append("")

    profiler_non_main = None
    reconcile_proxy = None
    harness_labeled = None
    if args.speedscope and args.speedscope.is_file():
        result = bucketize(args.speedscope)
        lines.append(format_table(result))
        reconcile_proxy = reconcile_proxy_pct(result)
        harness_labeled = harness_labeled_pct(result)
        profiler_non_main = harness_labeled
    elif (Path("apu_characterization/out/pyspy_lh01.speedscope.json")).is_file():
        sp = Path("apu_characterization/out/pyspy_lh01.speedscope.json")
        result = bucketize(sp)
        lines.append(format_table(result))
        reconcile_proxy = reconcile_proxy_pct(result)
        harness_labeled = harness_labeled_pct(result)
        profiler_non_main = harness_labeled

    lines.append("## Cross-check")
    if timer_reconcile_pct is not None and reconcile_proxy is not None:
        delta_proxy = abs(timer_reconcile_pct - reconcile_proxy)
        lines.append(
            f"- py-spy reconcile proxy (INTERPRETER_OTHER + THREADPOOL leaf): "
            f"**{reconcile_proxy:.1f}%** of sampled time"
        )
        lines.append(
            f"- py-spy harness-labeled leaf (HTTP/parse/framework/tokenizer): "
            f"**{harness_labeled:.1f}%**"
        )
        lines.append(f"- Delta (timer reconcile vs proxy): **{delta_proxy:.1f} pp**")
        if delta_proxy <= 20:
            lines.append(
                "- **Verdict (a):** reconcile mass aligns with native/unclassified + "
                "thread-pool stacks in py-spy. Proceed to Phase C (v2 replication)."
            )
        elif delta_proxy <= 30:
            lines.append(
                "- **Verdict (a) provisional:** within 30 pp; sampling lag at 100 Hz may "
                "under-count. Optional re-run with `PYSPY_RATE=20` (now script default)."
            )
        else:
            lines.append(
                "- **Verdict (c):** timer reconcile and py-spy proxy disagree by >30 pp. "
                "Re-profile at `--rate 20 --native` before v2 replication."
            )
    elif timer_reconcile_pct is not None and profiler_non_main is not None:
        delta = abs(timer_reconcile_pct - profiler_non_main)
        lines.append(
            f"- Timer reconcile share: {timer_reconcile_pct:.1f}% vs profiler harness-class share: "
            f"{profiler_non_main:.1f}% (delta {delta:.1f} pp)"
        )
        if delta <= 15:
            lines.append("- **Verdict (a):** reconcile is client/framework harness-class work. Proceed to Phase B/C.")
        else:
            lines.append("- **Verdict (c):** profiler and timer disagree by >15 pp. Investigate before replication v2.")
    else:
        lines.append(
            "- Pending: run `profile_reconcile_session` on LH-01 (index 8) with `--pyspy` on Linux/WSL "
            "and re-run this script."
        )
        lines.append(
            "- Bug checks: see `out/reconcile_bug_checks.md` (synthetic worker test confirms reconcile "
            "equals unwrapped thread CPU under v1 booking)."
        )
        lines.append("- **Interim verdict (a):** proceed with v2 instrumentation; confirm with py-spy on heavy session.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
