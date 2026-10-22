# Task BF analysis files (calibration values for the DEMO-2 freeze)

- freeze_values.json: tools/demo2_freeze_values.py output (P' rule PF 6, A/A PF 8, cloud cap PF 9,
  LOW_MEM PF 10, per-run facts) with the sha256 of each input .sealed.
- calib_replay_{T2S,XPS}.json (+ .stdout.txt): tools/demo2_iso_quality_replay.py at 24f9ed9 on
  DEMO2_CALIB_30. Pipeline check only; no threshold is tuned on it. No refusals.
- calib_replay_*_SCORER_REUSE_BUG.*: the same command at 5212e66, before the scorer fix. Kept as the
  evidence for 24f9ed9: A2 vs A on byte-identical local logs gave splice dC_iso -0.0042 (6 vs 5 base
  passes). Not used for any value.
