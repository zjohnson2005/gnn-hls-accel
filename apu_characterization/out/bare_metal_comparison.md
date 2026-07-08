# Bare-metal validation: WSL2 v3.1 vs native comparison

- baseline: `replication_remote_search_v3.json` (platform wsl2, commit `d5fd7b8b`)
- native:   `bare_metal_validation_native_vm.json` (platform native_vm, commit `8b84ddfa`, kernel `6.8.0-124-generic`)
- native validity: publishable

## Table 1: per-task medians side by side

| task | host CPU ms (wsl2 / native / rel delta) | LLM wait s (wsl2 / native) | category | share pp (wsl2 / native / abs delta) |
|------|------------------------------------------|----------------------------|----------|----------------------------------------|
| LH-01 | 543.7 / 523.8 / -4% | 19.79 / 17.62 | TOOL_COMPUTE | 30.8 / 39.2 / 8.4 |
|  |  |  | THREADPOOL | 5.6 / 3.7 / 2.0 |
|  |  |  | ORCH_SETUP | 3.8 / 2.2 / 1.6 |
|  |  |  | ORCH_DISPATCH | 28.6 / 11.2 / 17.4 |
|  |  |  | CLIENT_HTTP | 8.1 / 5.8 / 2.3 |
|  |  |  | FRAMEWORK | 10.5 / 9.1 / 1.4 |
|  |  |  | TOKENIZATION | 10.2 / 3.6 / 6.6 |
| RH-01 | 222.0 / 161.7 / -27% | 8.87 / 7.41 | TOOL_COMPUTE | 40.8 / 46.1 / 5.3 |
|  |  |  | THREADPOOL | 37.0 / 32.2 / 4.8 |
|  |  |  | ORCH_SETUP | 8.3 / 6.0 / 2.2 |
|  |  |  | ORCH_DISPATCH | 2.9 / 3.8 / 0.9 |
|  |  |  | CLIENT_HTTP | 2.0 / 2.3 / 0.2 |
|  |  |  | FRAMEWORK | 5.2 / 5.4 / 0.3 |
|  |  |  | TOKENIZATION | 2.6 / 3.0 / 0.4 |
| FO-01 | 134.0 / 79.5 / -41% | 9.36 / 7.94 | THREADPOOL | 31.6 / 28.3 / 3.3 |
|  |  |  | ORCH_SETUP | 13.1 / 13.4 / 0.3 |
|  |  |  | ORCH_DISPATCH | 8.4 / 8.8 / 0.4 |
|  |  |  | CLIENT_HTTP | 4.4 / 4.8 / 0.4 |
|  |  |  | HTTP_CLIENT | 1.6 / 1.6 / 0.0 |
|  |  |  | FRAMEWORK | 15.3 / 20.2 / 4.9 |
|  |  |  | TOKENIZATION | 8.3 / 8.7 / 0.4 |
|  |  |  | RESIDUAL_UNATTRIBUTED | 7.9 / 8.0 / 0.1 |
| RE-01 | 94.3 / 48.6 / -48% | 14.21 / 10.20 | TOOL_COMPUTE | 2.9 / 4.2 / 1.3 |
|  |  |  | THREADPOOL | 14.4 / 14.3 / 0.1 |
|  |  |  | ORCH_SETUP | 19.3 / 19.9 / 0.5 |
|  |  |  | ORCH_DISPATCH | 27.8 / 28.1 / 0.3 |
|  |  |  | CLIENT_HTTP | 9.1 / 11.9 / 2.8 |
|  |  |  | FRAMEWORK | 10.0 / 12.3 / 2.3 |
|  |  |  | TOKENIZATION | 8.8 / 8.5 / 0.2 |
| CH-01 | 49.8 / 35.2 / -29% | 5.58 / 3.86 | TOOL_COMPUTE | 4.5 / 6.4 / 1.9 |
|  |  |  | THREADPOOL | 14.3 / 16.5 / 2.2 |
|  |  |  | ORCH_SETUP | 38.9 / 31.8 / 7.0 |
|  |  |  | ORCH_DISPATCH | 16.2 / 17.2 / 1.0 |
|  |  |  | CLIENT_HTTP | 10.0 / 11.0 / 0.9 |
|  |  |  | FRAMEWORK | 8.4 / 11.0 / 2.6 |
|  |  |  | TOKENIZATION | 5.6 / 5.9 / 0.3 |
| LH-02 | 14.4 / 8.3 / -42% | 5.48 / 4.77 | ORCH_SETUP | 76.9 / 73.9 / 3.0 |
|  |  |  | CLIENT_HTTP | 10.7 / 13.5 / 2.8 |
|  |  |  | FRAMEWORK | 8.4 / 8.4 / 0.0 |
|  |  |  | TOKENIZATION | 3.6 / 4.0 / 0.5 |

## Table 2: scheduling-sensitive focus (THREADPOOL, FRAMEWORK, ORCH_DISPATCH)

| task | category | wsl2 share pp | native share pp | delta pp |
|------|----------|---------------|-----------------|----------|
| LH-01 | THREADPOOL | 5.6 | 3.7 | -2.0 |
| LH-01 | FRAMEWORK | 10.5 | 9.1 | -1.4 |
| LH-01 | ORCH_DISPATCH | 28.6 | 11.2 | -17.4 |
| RH-01 **(headline)** | THREADPOOL | 37.0 | 32.2 | -4.8 |
| RH-01 | FRAMEWORK | 5.2 | 5.4 | +0.3 |
| RH-01 | ORCH_DISPATCH | 2.9 | 3.8 | +0.9 |
| FO-01 | THREADPOOL | 31.6 | 28.3 | -3.3 |
| FO-01 | FRAMEWORK | 15.3 | 20.2 | +4.9 |
| FO-01 | ORCH_DISPATCH | 8.4 | 8.8 | +0.4 |
| RE-01 | THREADPOOL | 14.4 | 14.3 | -0.1 |
| RE-01 | FRAMEWORK | 10.0 | 12.3 | +2.3 |
| RE-01 | ORCH_DISPATCH | 27.8 | 28.1 | +0.3 |
| CH-01 | THREADPOOL | 14.3 | 16.5 | +2.2 |
| CH-01 | FRAMEWORK | 8.4 | 11.0 | +2.6 |
| CH-01 | ORCH_DISPATCH | 16.2 | 17.2 | +1.0 |
| LH-02 | THREADPOOL | 0.0 | 0.0 | +0.0 |
| LH-02 | FRAMEWORK | 8.4 | 8.4 | -0.0 |
| LH-02 | ORCH_DISPATCH | 0.0 | 0.0 | +0.0 |

## Table 3: instrument health

| task | wsl2 residual % | native residual % |
|------|-----------------|-------------------|
| LH-01 | 0.0 | 0.0 |
| RH-01 | 0.0 | 0.0 |
| FO-01 | 7.9 | 8.0 |
| RE-01 | 0.0 | 0.0 |
| CH-01 | 0.0 | 0.0 |
| LH-02 | 0.0 | 0.0 |

- native timer overhead: 9269.73089 ns per timed pair
- native loadavg (1-min) start 0.008, end 0.002; per-session records in the native artifact
- timer resolution self-test and instrumentation unit tests are run-gates on the native box; a native artifact exists only if they passed

## Verdict: DELTA

Category shares shifted beyond 10 pp between the 8-core WSL2 baseline and the 4 vCPU native VM:

- LH-01/ORCH_DISPATCH: 28.6 pp (wsl2) vs 11.2 pp (native)

**Limitations sentence for the main report:** "THREADPOOL share differs on a 4 vCPU native VM relative to the 8-core WSL2 baseline; platform vs core-count effects are not separated in this check."

The WSL2 caveat stays as-is. No rerun is triggered: no WSL2 matched-core rerun, no dual-boot, unless a future phase needs scheduling categories at paper grade.
