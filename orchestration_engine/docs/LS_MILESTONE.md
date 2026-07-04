# LightningSim milestone pack (Jul 2026)

## Proved on ece-rschsrv

- **TRACE OK:** 540 lines, 2 FIFOs on `gcn_stream_proj/sol1`
- **DSE:** `source: lightningsim`, 500 evaluations, 0 deadlocks, baseline latency 315 cycles, 262 Pareto points
- **trace.pkl:** written by `ls_probe` (~802 bytes)
- **Vitis csim:** TEST PASSED for `GNN_LS_LITE` build (`run_hls_stream_ls.tcl`)

## Known limitation

LS instrumented testbench: all Y=0 (exit 1). Functional oracle = Vitis csim, not LS.
FIFO timing DSE does not require LS golden match.

## Toolchain split

| Purpose | Vitis | Entry |
|---------|-------|--------|
| Thesis ap_fixed cosim | 2025.2.1 | `run_hls_stream.tcl`, `hls_env.sh` |
| LS trace + DSE | ARCHIVE 2023.1 | `run_hls_stream_ls.tcl`, `hls_env_lightningsim.sh` |

## Quick run (Vitis box)

```bash
export CONDA_PREFIX=$HOME/miniconda3/envs/fifo-advisor
export PATH="$CONDA_PREFIX/bin:$PATH"
bash orchestration_engine/run_ls_probe.sh
python -m orchestration_engine.eval.dse_sweep \
  --solution-dir gcn_stream_proj/sol1 --n-samples 500 \
  --output orchestration_engine/characterization/out/phase2/dse_report.json
```

## Patch target (conda env)

`$CONDA_PREFIX/lib/python3.12/site-packages/lightningsim/runner.py`  
Applied by: `python -m orchestration_engine.eval.patch_lightningsim`

## Files in this zip

See `MANIFEST.txt` in the zip root.

## Copy from server separately (not in git)

- `gcn_stream_proj/sol1/trace.pkl`
- `gcn_stream_proj/sol1/.oe_lightningsim_vitis`
- `orchestration_engine/characterization/out/phase2/dse_report.json`
- `ls_probe.log`
