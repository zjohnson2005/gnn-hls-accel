# CAP-3 arm 1 (8B) — boundary findings (INF-6 consolidation)

**Status:** unsealed evidence retained as contaminated sessions (not deleted)  
**Recorded UTC:** 2026-09-20T16:47:38.513754+00:00  
**Model:** `configs/models/Qwen3-8B-int4-ov.yaml`  
**Machine-readable:** `derived/cap3/ARM1_8B_BOUNDARY_FINDINGS.json`

## Two-boundary statement

8B gpu_only_f16 TTFT limit sits between **n=3000** (passes) and **n=5500** (thrashes / fails).

1. **Paging / thrash zone** — allocation can succeed but the system pages (n≈5500; long n=10000 under the old 1800 s parent timeout).
2. **Hard GPU allocation ceiling** between **5500 and 8000** — probes refuse in ~12–15 s with `RuntimeError`.

## Operator-stated vs on-disk

| n | Operator summary | On-disk CL_OUT_OF_RESOURCES? |
|---|---|---|
| 3000 | passes, ~11 s | n/a (pass; prefill ~2.9 s) |
| 5500 | thrash commit ~6.9 GB / ~3.0 GB resident / 24+ min killed | **YES** on written fails |
| 8000 | RuntimeError 12–15 s, 3/3 | **NO** — `could not execute a primitive` |
| 10000 | thrash ≤1800 s then fast refuse | **MIXED** (primitive and CL_OOR) |
| 6500 | fail after thrash | **YES but CONTAMINATED** |

## Verbatim errors (representative)

### n=8000 (21dd r0) — NOT CL_OUT_OF_RESOURCES

```
Exception from src\inference\src\cpp\infer_request.cpp:224:
Exception from src\plugins\intel_gpu\src\graph\impls\onednn\primitive_onednn_base.h:550:
could not execute a primitive


```

### n=5500 (21dd r0) — IS CL_OUT_OF_RESOURCES

```
Exception from src\inference\src\cpp\infer_request.cpp:224:
Exception from src\plugins\intel_gpu\src\runtime\ocl\ocl_common.hpp:62:
[GPU] CL_OUT_OF_RESOURCES exception.
	Due to a driver bug, any subsequent OpenCL API call may cause the application to hang, so the GPU plugin may be unable to finish correctly.
	The CL_OUT_OF_RESOURCES error typically occurs in two cases:
	1. Insufficient memory for the current inference.
	2. An out-of-bounds access to GPU memory from a kernel.
	For case 1 (Insuffi
```

### n=10000 (9c03 r0) — NOT CL_OUT_OF_RESOURCES

```
Exception from src\inference\src\cpp\infer_request.cpp:224:
Exception from src\plugins\intel_gpu\src\graph\impls\onednn\primitive_onednn_base.h:550:
could not execute a primitive


```

### n=10000 (1269 r0) — IS CL_OUT_OF_RESOURCES

```
Exception from src\inference\src\cpp\infer_request.cpp:224:
Exception from src\plugins\intel_gpu\src\runtime\ocl\ocl_common.hpp:62:
[GPU] CL_OUT_OF_RESOURCES exception.
	Due to a driver bug, any subsequent OpenCL API call may cause the application to hang, so the GPU plugin may be unable to finish correctly.
	The CL_OUT_OF_RESOURCES error typically occurs in two cases:
	1. Insufficient memory for the current inference.
	2. An out-of-bounds access to GPU memory from a kernel.
	For case 1 (Insuffi
```

## Contaminated sessions

See `derived/cap3/CONTAMINATED_SESSIONS.json` / `.md`. Paths under `derived/c2_ttft/` retained.
