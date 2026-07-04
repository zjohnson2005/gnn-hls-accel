# Reproducibility map (artifact -> command -> toolchain -> machine)

Every number quoted in the Phase 2 gate must appear in this table. **Do not mix
toolchains:** hardware truth uses Vitis 2025.2.1; LightningSim trace/DSE uses
ARCHIVE Vitis 2023.1 + conda `fifo-advisor`.

| Artifact | Generating command | Toolchain | Machine |
|----------|-------------------|-----------|---------|
| `orchestration_engine/characterization/out/phase2/csynth_scatter.json` | `bash orchestration_engine/run_phase2_scatter_only.sh` (csynth stage) | Vitis 2025.2.1 via `hls_env.sh` | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_scatter.json` | `bash orchestration_engine/run_phase2_scatter_only.sh` | Vitis 2025.2.1 | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_stream.json` | `bash orchestration_engine/run_phase2_scatter_stream.sh` | Vitis 2025.2.1 | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_graph_load.json` | `bash orchestration_engine/run_phase2_graph_load.sh` | Vitis 2025.2.1 | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_scatter_banked.json` | `bash orchestration_engine/run_phase2_scatter_banked.sh` | Vitis 2025.2.1 | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/power_scatter.json` | `bash orchestration_engine/run_power.sh scatter` | Vivado impl on exported RTL | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/power_graph_load.json` | `bash orchestration_engine/run_power.sh graph_load` | Vivado impl on exported RTL | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/oe_bench.log` | `bash orchestration_engine/run_oe_bench.sh` | g++ C++17 (no Vitis) | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/dse_report.json` | `bash orchestration_engine/run_phase2_lightningsim.sh` | Must have `"source":"lightningsim"` + `gcn_stream_proj/sol1/trace.pkl` | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/dse_report_oe.json` | `bash orchestration_engine/run_phase2_lightningsim_oe.sh` | Must have `"source":"lightningsim"` + OE `trace.pkl` (no synthetic) | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/ls_gcn_eval.json` | `run_ls_validate_gcn.sh` (via `ls_capture_gcn_eval`) | Live `eval_solution_default` on GCN trace | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/ls_oe_eval.json` | `run_phase2_lightningsim_oe.sh` (via `ls_capture_oe_eval`) | Live eval on OE trace; must match DSE baseline | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/ls_validation.json` | C1 + C2 scripts; `passed` requires both | C1 ≤5%; C2 ≤15% (cross-toolchain) | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_gcn_stream_ls.json` | `bash orchestration_engine/run_ls_validate_gcn.sh` | Vitis 2023.1 ARCHIVE cosim | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_gcn_stream.json` | `bash orchestration_engine/run_gcn_stream_cosim.sh` | Vitis 2025.2.1 thesis ap_fixed (E2) | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/phase2_gate.md` | `bash orchestration_engine/run_phase2_sprint_remainder.sh` | mixed (see rows above) | ece-rschsrv |
| `orchestration_engine/build/oe_bench` | `bash orchestration_engine/build.sh` | g++ C++17 | ece-rschsrv |
| GCN cosim JSON (E2) | `vitis_hls -f run_hls_stream.tcl` | Vitis 2025.2.1 | ece-rschsrv |
| `cost_model_3d/out/oe_experiment.json` | `bash orchestration_engine/run_oe_cost_model_3d.sh` | Python 3.7+ (conda fifo-advisor on server) | any |
| `orchestration_engine/characterization/out/phase2/variants_results.json` | `bash orchestration_engine/run_phase2_variants.sh` | Vitis 2025.2.1 csynth subset | ece-rschsrv |
| Deferred gate refresh | `bash orchestration_engine/run_phase2_deferred.sh` | C1+C2 required; synthetic DSE rejected | ece-rschsrv |

**LightningSim gate rules:** `dse_report*.json` must have `"source":"lightningsim"`,
`deadlocks:0`, `evaluations >= 100`, a non-empty `pareto_frontier`, and a live
`trace.pkl` under `solution_dir`. Hand-copied/summarized reports are rejected —
every DSE artifact must be the direct output of a full `dse_sweep` run on the
server. `ls_gcn_eval.json` / `ls_oe_eval.json` must come from the SAME solution
as the corresponding DSE report (checked by `ls_validate`). `ls_validation.json`
must have `"passed":true` (C1+C2). Synthetic/offline DSE is for `fifo_pareto/`
demos only and may never be written under `characterization/out/phase2/`.

Local-only work: edit files under `orchestration_engine/hls/`, `tb/`, `eval/`,
`phase2_gate/`. Any step invoking `vitis_hls` or Vivado is **server-only**.
