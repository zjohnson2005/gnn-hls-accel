# CAP-01 capability-scaling arm

CAP-01 replays frozen real-model candidate pools through three loop harnesses
under matched latency streams and fixed task budgets. See
`../METHODOLOGY_CAP01.md` for claim scope, gate definitions, and the document
map (prompt aliases vs on-disk paths).

## Lifecycle

1. Assemble the five-domain licensed corpus, verifier pins, and generation configuration.
2. Generate at least 2,048 candidates per task using the offline OpenAI path.
3. Verify candidates and run the 50-shuffle calibration.
4. Lock the corpus, pool, classification, answer space, verifier, and generation hashes.
5. Run the WSL2 debug smoke.
6. Qualify a bare-metal host and measure G6 floors.
7. Execute the full matrix serially with resume markers.
8. Re-execute verifier verdicts, audit G1-G7, and analyze completed runs.

The source protocol is intentionally marked `template_requires_p0_lock`.
Measurement publication must refuse an unlocked protocol.

## Protocol lock

```bash
python apu_characterization/tools/lock_cap01_protocol.py \
  --corpus-manifest apu_characterization/out/cap01/corpus.json \
  --pool-manifest apu_characterization/out/cap01/pools/manifest.json \
  --classification-manifest apu_characterization/out/cap01/classification.json \
  --generation-config apu_characterization/out/cap01/generation_config.json \
  --verifier-pin-manifest apu_characterization/out/cap01/verifier_pins.json
```

The output is immutable. If any P0 input changes, write a new protocol version
and append the reason to the died-ledger instead of replacing the lock.

At P2 exit, record the serial-hours estimate using measured smoke constants:

```bash
python apu_characterization/tools/estimate_cap01_matrix.py \
  --setup-ms <measured> --cooldown-ms <measured> \
  --output apu_characterization/out/cap01/run_root_manifest.json
```

## Validity

WSL2 smoke is `debug_only`. The narrow `capability_scaling` class requires
real frozen pools, the locked protocol, a qualified bare-metal host, serial
measurement, n=5, and passing G1-G7. It licenses solve-rate-at-fixed-budget
claims only for this best-of-N verification loop and frozen task population.
