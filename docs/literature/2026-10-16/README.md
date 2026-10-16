# Literature and source reads, 2026-10-15/16 (Task AS)

Two research passes by Zach and Claude (Cowork), copied byte for byte from
~/seam_closeout_1013/research_20261016/. Only the report file was renamed
(spaces removed). Verdicts and wording rules: docs/RELATED_SEARCHES.md,
section "2026-10-16 true default and tuned profile".

| File | Original name | sha256 |
|---|---|---|
| DEMO2_CONTROL/openvino_defaults.md | same | c486409d116a8af4080ec3775a78b2e840f643756c590e82a33ba3560d2e2ab0 |
| DEMO2_CONTROL/default_baseline_norms.md | same | 73c935529a5e5c22cba5c7f96eda371818d67d7202e863bff1ca75d3a2551408 |
| TUNED_PROFILE/STRENGTHENING_THE_TUNED_PROFILE.md | "Strengthening the tuned profile.md" | 414f5b2056f6c1b8c18e9ac9f7d7c5869fed2ad8f66d3e3f7897487057ecfc00 |
| TUNED_PROFILE/openvino_latency_features.md | same | 4ce61afa85d982d0cd3dc4970783ff9812967780b580345a95c20a984b0615d3 |
| TUNED_PROFILE/physics_data_path.md | same | 67c435bd65288218738719f5442d741e956998f15f4ae3efb4e9359621c49afa |
| TUNED_PROFILE/agent_level_levers.md | same | be67784f160378b27e98c774b7d3882e6f527aeb17d026ed3ab4e542beda95b3 |

Reading notes:
- openvino_defaults.md is the source read (2026.2.1 tags) behind the i8 KV
  default and the latency scheduler config. It supersedes the 2026-10-15
  u4 reading.
- openvino_latency_features.md section 5 leans toward f16 KV for latency.
  The report (STRENGTHENING_THE_TUNED_PROFILE.md) rejects f16 once prefix
  caching is on (decode, memory and XPS context all worse). DEMO-2 follows
  the report.
- Every number in these notes is LITERATURE or DERIVED unless it carries
  one of our run_ids. The ~68 GB/s effective bandwidth, the 147 KB/token
  transient fit and the 40,960 chunk-cap leap are DERIVED and untested
  (DEMO-2 pilots P2, P3).
