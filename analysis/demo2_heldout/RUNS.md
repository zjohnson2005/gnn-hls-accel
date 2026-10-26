# DEMO-2 T2S held-out runs (Task BK closeout)

Records: derived/demo2_heldout/ (byte copies of the two T2S be_v2 windows; *.log force-added).
Pin: derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json. Seals re-verified on the Mac (tools/seal_verify.py).

| arm | cell | run_id | window | head | rc | seal | note |
|---|---|---|---|---|---|---|---|
| A (true default) | ho_a | 1f13b75e-f1e3-49e1-9a1b-25bd4655a0cc | 20261023_131037_be_v2 | 72e499f | 0 | MATCH | primary arm |
| P (8B INT8, T2S) | ho_p | 9eb71a3a-a0f6-433b-bb4b-c0bfb39f37cf | 20261023_131037_be_v2 | 72e499f | 0 | MATCH | primary arm |
| C (full tuned) | ho_c | 89676c43-ee0e-4aff-ab62-bb5dbeb1cfd9 | 20261023_131037_be_v2 | 72e499f | 0 | MATCH | F2 |
| R-full | ho_rfull | 188a34b8-de70-42ad-b824-d40e852a06d4 | 20261023_131037_be_v2 | 72e499f | 0 | MATCH | secondary |
| B (device-only) | ho_b | f20ec748-6a78-4b83-a021-98f95ac53414 | 20261024_175945_be_v2 (resume FROM=34) | cedb9d3 | 0 | MATCH | secondary; git_head deviation (DEMO2_RESUME_2026-10-23c) |
| I-4K | ho_i4k | d9873c58-18d5-4b19-a21f-cb1dd5804cdb | 20261024_175945_be_v2 | cedb9d3 | 1 | UNSEALED, no summary.json | crashed in the BFCL multi-turn checker (IndexError: model result list shorter than the turn index); secondary only |

- The first window stopped at 15:03:08 ET Oct 23 on a foreign python before ho_b (banned_detail empty).
- Hand-back (both windows): PYTHON_COUNT=0, tree clean.
- Shared cloud-only log ho_cloud (XPS row 30): NOT RUN (deferred until after Oct 27). The registered
  primary (P vs A dC_iso, splice) needs it, so the T2S primary is PENDING; the fixed sequence (PF 2)
  has not started.
