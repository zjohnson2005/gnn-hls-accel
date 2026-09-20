# CAP-3 contaminated sessions (INF-6)

**Policy:** mark contaminated, **do not delete**.  
**Recorded UTC:** 2026-09-20T16:47:38.513754+00:00

| session_id | path | contamination | retain |
|---|---|---|---|
| `9c037801-…` | `derived/c2_ttft/9c037801-342b-478e-8e95-5b66d369eab8` | post-thrash memory (n=6500 invalid) | yes |
| `1269eaca-…` | `derived/c2_ttft/1269eaca-adce-42ec-a164-eb09ba654b6b` | post-thrash memory (n=6500 invalid) | yes |
| `c3efd48e-…` | `derived/c2_ttft/c3efd48e-84c5-46c6-bb1f-42d13f7c0a16` | AC mid-run / FAIL_CANARY_DRIFT 8.3% | yes |
| `21dd48fb-…` | `derived/c2_ttft/21dd48fb-21e2-468a-be00-c41be1acfe22` | 1800 s timeout thrash class | yes |

**Genuine boundary data:** n=3000 pass; n=5500 thrash/CL_OOR; n=8000 fast RuntimeError; n=10000 refuse/thrash pattern.  
**Not genuine:** n=6500 after unrecovered thrash in first two sessions; bisect under AC loss on `c3efd48e`.
