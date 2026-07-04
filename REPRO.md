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
| `orchestration_engine/characterization/out/phase2/dse_report.json` | `bash orchestration_engine/run_phase2_lightningsim.sh` | Vitis 2023.1 ARCHIVE + conda via `hls_env_lightningsim.sh` | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/dse_report_oe.json` | `bash orchestration_engine/run_phase2_lightningsim_oe.sh` | Vitis 2023.1 ARCHIVE + conda | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/ls_validation.json` | `bash orchestration_engine/run_gcn_stream_cosim.sh` | Vitis 2025.2.1 cosim + LS trace/dse | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/cosim_gcn_stream.json` | `bash orchestration_engine/run_gcn_stream_cosim.sh` | Vitis 2025.2.1 | ece-rschsrv |
| `orchestration_engine/characterization/out/phase2/phase2_gate.md` | `python -m orchestration_engine.phase2_gate.gate_report` | Python 3 (local or server) | any |
| `orchestration_engine/build/oe_bench` | `bash orchestration_engine/build.sh` | g++ C++17 | ece-rschsrv |
| GCN cosim JSON (E2) | `vitis_hls -f run_hls_stream.tcl` | Vitis 2025.2.1 | ece-rschsrv |
| `cost_model_3d/out/oe_experiment.json` | `bash orchestration_engine/run_oe_cost_model_3d.sh` | Python 3.7+ (conda fifo-advisor on server) | any |

Local-only work: edit files under `orchestration_engine/hls/`, `tb/`, `eval/`,
`phase2_gate/`. Any step invoking `vitis_hls` or Vivado is **server-only**.
