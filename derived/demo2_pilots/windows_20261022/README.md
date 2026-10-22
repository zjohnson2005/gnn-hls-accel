# DEMO-2 windows 2026-10-21/22 (closed out in Task BF, Mac only, $0)

Byte copies (-text) of the queue output folders under ~/seam_closeout_1013/. Runner cells carry their
own .sealed files. Task BF re-verified every h1 seal on the Mac with the runner's tree hash
(tools/run_h1_hybrid._sha256_tree): 19 of 19 OK.

| folder | what | run_ids |
|---|---|---|
| t2s_downloads_20261021_2215/ | T2S model fetch, Oct 21 22:15 ET | 8B INT4 ir_sha256 cd97874b... MATCH; 8B INT8 eac56228... MATCH |
| xps_downloads_0653/ | XPS model fetch, Oct 22 06:53 ET | 8B INT4 cd97874b... MATCH; 4B INT8 f7d323d0... MATCH |
| t2s_0654_ladder/ | T2S R0 readbacks + R1 budget ladder (head 145047f); R3/R4 NOT_BUILT | R0 5fe2d65d, 13cca5ff, d2a8c095, b13a7060 (verdict valid); R1 i8 5a6583aa-9127-41f4-b233-0e61690ae443 (refined_largest_pass 16,384), R1 u4 7f36c923-2ad2-4862-8d3f-7018170c4897 (16,384, observation only) |
| xps_0656_ladder/ | XPS L0 readback, R0 readbacks, R1 ladder | R0 9bcfdc51, 8efcb6dd (valid); R1 i8 dd2ecf51-abf1-42a9-94d6-ed9c863ef42e (8,192), R1 u4 ab95aeb2-3262-4423-a08f-051fd5aad43a (8,192) |
| t2s_1012_be/ | T2S calibration, DEMO2_CALIB_30, local-only, head 145047f | cal_a1 75fa4d1c-3b4a-47fc-b238-d288dfef036f, cal_a2 000010fc-1f14-4ac3-93ae-dc1b1dc41d98, cal_c dd62e520-4284-4e5b-9e44-d92c46070f14, cal_p (8B INT8) c91bc055-2978-4816-89fb-c81523bff8a6 |
| xps_1012_be/ | XPS calibration part 1; stopped 11:10:39 AM by the banned-app check (msedge) after cal_a1 | cal_a1 7cf9b18d-ffab-4833-bd29-44b7e553455f |
| xps_1149_be/ | XPS calibration part 2 (FROM=11 UNTIL=14) | cal_a2 7d4e5117-49ad-4068-8b0a-61e786308cef, cal_c a200bd1a-b80b-432d-bdd5-2b1d6cab01f7, cal_p (8B INT4) f511af02-6c89-4818-b984-2ca3ebf4b1aa, cal_pp (4B INT8) 4407accc-77c2-4891-8669-4951e8ffc49e |
| xps_1901_be_v2_cal_cloud/ | calibration cloud-only log, v2 queue, head 5212e66 (cache-aware CostGuard; plan.json cloud_price_formula present) | cal_cloud a403befe-deac-418e-82c9-db9260fa809b ($2.4522 repriced = logged; 22/30 cloud pass) |

- Every calibration cell: status complete, 30/30 entries, no watchdog fire, no hang recorded, no
  Traceback/REFUSED in the worker logs, no generation errors, 0 LOW_MEM turns (PF 10).
- The *.log files are gitignored and force-added, as in earlier closeouts.
- The cal_cloud window recorded chrome.exe started 7:03 PM after the window's own reboot
  (banned_detail.txt, parent explorer.exe). The v2 script logs and stops these after its reboot.
- Values computed from these records: analysis/demo2_pilots/BF/ and
  docs/amendments/DEMO2_FREEZE_2026-10-23.md.
