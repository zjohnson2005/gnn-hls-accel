# MCP-01 protocol-tax arm

The source contracts are `protocol_v1.json`, `contracts.py`, and
`taxonomy.py`. Measurement thresholds and matrix membership are protocol
inputs, not values inferred from results.

## Development gate

```bash
bash apu_characterization/bootstrap_mcp.sh
bash apu_characterization/run_mcp_gate.sh
```

WSL2 is permitted for unit and integration smoke only. Smoke artifacts must
remain `debug_only`.

The data-independent bundle check can also be run directly after activating
the pinned environment:

```bash
python apu_characterization/tools/check_mcp_bundle.py
```

It checks required source files, exact installed dependency pins, the frozen
120/160 matrix sizes, seeds 0–4, the real execution callback, and the WSL
publication refusal. It does not require retained measurements.

## Matrix inspection

```bash
python -m apu_characterization.experiments.mcp_tax_matrix
```

The command defaults to dry-run and prints the frozen 120-cell matrix (160
when streamable HTTP has passed its admission smoke).

## Bare-metal publication run

On the native Linux host, set disjoint core lists and run:

```bash
export MCP_OS_CORES=0,1
export MCP_CLIENT_CORES=2
export MCP_SERVER_CORES=4
bash apu_characterization/run_mcp_bare_metal.sh
```

The launcher refuses WSL/VM publication mode, dirty tracked files, invalid
core partitions, wrong dependency lock, and concurrent measurement. Do not
parallelize cells or seeds.

Run data is retained under:

```text
apu_characterization/out/mcp_tax/runs/
  {transport}/{cell_id}/{seed}/{client,server}/
```

Analysis may fan out only after measurement directories are complete.

Postprocess a retained run root after the serial launcher exits:

```bash
bash apu_characterization/postprocess_mcp.sh \
  apu_characterization/out/mcp_tax/runs
```

The postprocessor takes the same exclusive host lock used by measurement,
audits completed run directories in parallel, and writes
`mcp_tax.matrix.json`, `mcp_tax.report.md`, and `mcp_tax.figure.png` beside
`runs/`. It then runs the publication validator and fails closed if any gate
is not satisfied. Postprocessing never launches measurement callbacks.

## Validity

Passing native runs use `protocol_microbenchmark`, a narrow publication class
for MCP protocol/transport CPU and wait tax. It is not a live-agent result.
External 12.4/23.7/8.3 ms reference values remain in a separate report
section and are never represented as measurements from this repository.
