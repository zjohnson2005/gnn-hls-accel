# Configuration provenance of cited numbers (Task AZ, 2026-10-20)

Rithwik item 1. For each number we cite: how the pipeline was actually
constructed, and what else could differ. No number is changed here.
Machine-readable rows, with every run dir, seal status, version and date:
`derived/audit/CONFIG_PROVENANCE.json` (built by
`analysis/audit/config_provenance_az.py` from committed run dirs).

## How the four classes are built (GenAI 2026.2.1)

| class | construction | prefix caching | max_num_batched_tokens |
|---|---|---|---|
| TRUE_DEFAULT | `LLMPipeline(model, "GPU")`, no property, no SchedulerConfig: GenAI's latency scheduler | on | SIZE_MAX |
| PLAIN_PIPELINE_WITH_PROPS | the same latency scheduler, plus properties (KV_CACHE_PRECISION, CPU pinning, NPU prompt length, prompt_lookup) | on | SIZE_MAX |
| REPLACED_SCHEDULER | `sc = SchedulerConfig(); sc.enable_prefix_caching = False`, passed as `scheduler_config`: struct defaults replace the latency scheduler | off | 256 |
| EXPLICIT | a full SchedulerConfig with every field given (P3 `--sched-*` cells, P10 cells) | as given | as given |

Both scheduler sets were read back by P0a: 597f40a9 (XPS, 2026-10-16) and the
T2S readback of 2026-10-20 (derived/demo2_pilots/p0a_readback_t2s_20261020/).
Latency default: prefix caching on, max_num_batched_tokens 18446744073709551615,
cache_size 0, dynamic_split_fuse on, no eviction. Struct default: prefix
caching off, 256, max_num_seqs 256, cache_size 0, split-fuse on, no eviction.
Compiled KV: no property -> i8; u8 request -> the same i8 (int8 on all 72
ports); u4 -> u4; f16 -> f16. For runs before P0a the compiled type is
DERIVED from that readback on the same OpenVINO build; it was not read back in
the run itself. CACHE_DIR: none in any cited run (it breaks arm A, 3a03221e).

## Table

OV = openvino 2026.2.1-21919 + openvino_genai 2026.2.1.0-3123, as recorded in
the run, unless marked. Host from the model path in the run
(C:\Users\zjohn = XPS aipc-c1, C:\Users\zach = T2S evo-t2).

| number | run_id(s) | date (UTC) | host | tool | class | KV req -> compiled | residency | GPU driver | recommendation |
|---|---|---|---|---|---|---|---|---|---|
| resident limit 15,000 (f16) | 553b3a5c | 2026-09-30 | XPS | run_resident_limit | PLAIN_PIPELINE_WITH_PROPS | f16 -> f16 | RESIDENT two-turn | UNKNOWN (8724 on 09-16, 8860 on 10-20) | label; re-measure (cmd 2) |
| resident limit 20,000 (i8/u8) | cf3555d5 | 2026-09-30 | XPS | run_resident_limit | PLAIN_PIPELINE_WITH_PROPS | u8 -> i8 | RESIDENT two-turn | UNKNOWN (same) | label "plain pipeline + u8 property"; re-measure (cmd 1) |
| resident limit 26,500 (u4) | e4a22dac | 2026-10-01 | XPS | run_resident_limit | PLAIN_PIPELINE_WITH_PROPS | u4 -> u4 | RESIDENT two-turn | UNKNOWN (same) | label; re-measure (cmd 3) |
| resident limit 18,000 (true default) | a5d19dcc | 2026-10-20 | XPS | run_resident_limit (P3 cell 0) | TRUE_DEFAULT | none -> i8 | RESIDENT two-turn | 8860 (read same day) | cite as the true-default limit |
| warm turn-2 at 12k: f16 0.639 / u8 1.003 / u4 0.946 s | 72776603, 1587d2f4, dd2b0779 | 2026-09-30 | XPS | run_warm_kv | PLAIN_PIPELINE_WITH_PROPS | f16 / u8 -> i8 / u4 | RESIDENT two-turn, delta 183 | UNKNOWN | label; no true-default point exists (cmd 4) |
| DEMO-1 V4 $0.184 (XPS) vs $0.0129 (T2S) per task | a678926e, 30caa847 | 2026-10-13 / 10-14 | XPS / T2S | run_h1_hybrid slo_escalate | REPLACED_SCHEDULER | u8 -> i8 | NON_RESIDENT | UNKNOWN both | label exactly (below); re-measure needs spend |
| DEMO-1 V1 (local 0.0, MATCH x3) | f7343708, b026f3fd | 2026-10-13 | XPS / T2S | same | REPLACED_SCHEDULER | u8 -> i8 | NON_RESIDENT | UNKNOWN | label |
| cold edge 10,000 (9,750 HELD) | c2246b1f (c647f0c7 HELD) | 2026-09-24 | XPS | c2_ttft, one child per repeat | PLAIN_PIPELINE_WITH_PROPS | u8 -> i8 | cold single generate | UNKNOWN | label |
| placement 21.4x (GPU 10,000 vs CPU 468) | c2246b1f, 7f232f86 | 2026-09-24/25 | XPS | c2_ttft | PLAIN_PIPELINE_WITH_PROPS (CPU: PCORE_ONLY, pinning, 4 threads) | u8 -> i8 / CPU none | cold | UNKNOWN | label |
| int8 decodes 30-34% slower | 180dfbb9 | 2026-09-30 | XPS | run_decode_match | PLAIN_PIPELINE_WITH_PROPS | u8 -> i8 | cold | UNKNOWN; OV not recorded | label |
| 46k cold turn 230-253 s | 2b3316b6 | 2026-09-16 | XPS | cap4 | PLAIN_PIPELINE_WITH_PROPS | f16 / u8 / u4 | RESIDENT (interleaved) | 8724 (recorded in run) | label; OV not recorded |
| ~46,000 combined limit; C2 23-25x | none in repo | - | - | - | UNKNOWN | - | - | - | NEEDS RUN_ID (Zach); cannot be audited |
| P0-v2 warm TTA 2.47/3.26 s GPU, 9.29/11.17 s CPU | ac4e5472 | 2026-10-01 | XPS | exchange_rate | PLAIN_PIPELINE_WITH_PROPS | u8 -> i8 (CPU u8) | RESIDENT two-turn | UNKNOWN | label |
| NPU 1024->960, 2048->1984, 4096->4032 | faa14a31; 9acabbf7, 2ffbd61c; 2972e8c4 | 2026-10-14/15 | **T2S** | npu limit ladder | PLAIN_PIPELINE_WITH_PROPS (MAX_PROMPT_LEN, MIN_RESPONSE_LEN 8, NPUW_LLM_PREFILL_CHUNK_SIZE 1024; no scheduler) | INT8 weights | n/a | NPU driver UNKNOWN (4512 on 10-20) | label with the host |

DEMO-2 pilot runs of 2026-10-19/20 (all OV as above, $0):
- TRUE_DEFAULT, compiled KV read in-run (PA, i8): arm A (-RequireTrueDefault)
  640ec474, 39c1c131, 841b84e4, 24c1abc0, 15367c3a (XPS); 03632ad3, b90f1d5b,
  09932887, 1a634610, daa6c026, bbdd1c0d (T2S).
- TRUE_DEFAULT, KV not read in-run: P9 687bbb9f (XPS), 63b2567a (T2S);
  P2 i8 29209e26 (T2S).
- PLAIN_PIPELINE_WITH_PROPS (u4, compiled read in-run): P8-u4 1f3a261a,
  162a9b5c (XPS), 6c610aa6, 3aa565da, 108d5f43 (T2S); P4 16996cdb, 4d8e2fb1,
  cc32619a (u4 + prompt_lookup K3/K5, T2S). P2 u4 0a55c316 and f16 aa01040d
  (T2S; KV not read in-run).
- EXPLICIT: P10 C1 027a07b7 (prefix caching off, max_num_batched_tokens
  SIZE_MAX restated, --sched-exploratory; XPS).
- Driver: XPS 8860 and T2S 8509 were read on 2026-10-20 before these runs;
  for 2026-10-19 (AW window) the XPS driver is UNKNOWN.

## What DEMO-1 V1-V4 replaced

Every DEMO-1 V cell on both hosts (f7343708, 1acc8c58, 71d33f7a, ab88f47f,
a678926e; b026f3fd, a4284ab0, 30caa847) ran NON_RESIDENT with KV u8. The plan
records `scheduler_config.source = explicit_SchedulerConfig`,
`enable_prefix_caching false`; the code at each recorded head (4281755a,
ed292054, d15fe09e, 22580745, c80c2fbe, d481bf28, 63e36a94) builds
`SchedulerConfig()` and sets only prefix caching. Against the latency default it
changed two fields: prefix caching on -> off, and max_num_batched_tokens
SIZE_MAX -> 256. The other fields (cache_size 0, split-fuse on, no eviction)
are equal. With split-fuse on and 256 per batch, prefill runs in 256-token
chunks, which the latency default does not do. Wording: "NON_RESIDENT, bare
SchedulerConfig (prefix caching off, max_num_batched_tokens 256), KV u8
(compiles i8)". It is not the runtime default, and the DEMO-2 arm A contrast
(true default, RESIDENT) changes residency and scheduler together.

## Two confounds to report separately

1. cf3555d5 is a plain LLMPipeline (latency scheduler) with a KV u8 property,
   not the replaced config (Task AX). The resident-limit numbers are therefore
   PLAIN_PIPELINE_WITH_PROPS, not TRUE_DEFAULT and not REPLACED_SCHEDULER.
2. The XPS GPU driver changed: 32.0.101.8622 (probe 2026-07-29) ->
   32.0.101.8724 (2b3316b6, 2026-09-16) -> 32.0.101.8860 (2026-10-20; INF date
   2026-06-24). The install date of 8860 is not recorded, so every XPS run
   from 2026-09-17 to 2026-10-19 has an UNKNOWN driver (8724 or 8860).
   cf3555d5 (20,000, u8) and a5d19dcc (18,000, no property) differ in both the
   property and possibly the driver; their baseline available memory is the
   same (about 10.7 GB) and both ladders are monotonic. The 2,000-token gap is
   not attributed.

## Seal status on this Mac

Seals made before the `-text` policy were committed LF-normalized; their
hashes are of the CRLF bytes. 553b3a5c, cf3555d5, e4a22dac, 72776603,
1587d2f4, dd2b0779, 180dfbb9, ac4e5472 (MATCH_MANIFEST) and c2246b1f, 7f232f86,
2b3316b6 (MATCH) verify after CRLF restore; as checked out they read
MANIFEST_COVERAGE_GAP / MISMATCH. The cited a678926e tree
(sealed_slo_escalate_a678926e) is MATCH; its working copy
slo_escalate_a678926e reads MISMATCH even after CRLF restore (it carries an
H1-format .sealed; not investigated, not the cited tree).

## Re-measure commands ($0, XPS; each needs Zach's OK and a fresh boot)

`<R>`, `<PY>` as in docs/amendments/DEMO2_PILOTS_2026-10-16.md section 5.
Times DERIVED from a5d19dcc (13.2 min for 9 rungs) and 72776603.
1. u8 on the current driver (splits the 20,000 vs 18,000 gap):
   `XPS 'cd <R>; powershell -NoProfile -File tools\spawn_detached.ps1 -CommandLine "<PY> -u tools\run_resident_limit.py --arm gpu_only_u8 --model-spec configs\models\Qwen3-4B-int4-ov.yaml --high 50000" -LogPath derived\c2_ttft\_launches\audit_az\u8_limit.log -WorkingDirectory <R>'` (~14 min).
2. f16: the same with `--arm gpu_only_f16 --high 30000` (~14 min).
3. u4: the same with `--arm gpu_only_u4 --high 50000` (~15 min; or take it from the P3 u4 cells).
4. Warm turn-2, true default: `... tools\run_warm_kv.py --arm gpu_only --model-spec configs\models\Qwen3-4B-int4-ov.yaml --n-cached 12000,24000,46000 --delta-tokens 183 ...` (~20 min DERIVED; 46,000 is above the 18,000 limit and will fail, which is recorded).
Total about 65 min, two boot windows (the 7,200 s uptime gate). On the T2S the
same four take about the same time with `-T2S` gates and the UNCOLD deviation;
not proposed (Rithwik's block ends Oct 25).
