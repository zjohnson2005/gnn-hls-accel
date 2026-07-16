from __future__ import annotations

from pathlib import Path

from apu_characterization.turntrace_v2.d5_report import build_report, load_cloud_full_corpus, render_markdown


def test_d5_report_idempotent_on_cloud_full() -> None:
    root = Path("apu_characterization/out/turntrace_v2/cloud_full")
    if not root.exists():
        return  # CI without artifacts
    a = build_report(load_cloud_full_corpus(root), corpus_root=root)
    b = build_report(load_cloud_full_corpus(root), corpus_root=root)
    assert a["prefixspan"]["overall"]["agreement_rate"] == b["prefixspan"]["overall"]["agreement_rate"]
    assert a["level2_call_shape_table"] == b["level2_call_shape_table"]
    assert "Level 2" in render_markdown(a)
    assert all(not row["unstable_n_lt_3"] for row in a["level2_call_shape_table"])
    assert a["methods"]["n_calls"] == 160
