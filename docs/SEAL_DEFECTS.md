# Seal defects

Recorded defects in sealed artifacts. Seals themselves are write-once —
this file is the place a reader finds the reconstruction, not a patch to
the seal.

---

## SD-001 — `41e419bd` records no model-spec path or `ir_sha256`

| field | value |
|---|---|
| session / seal | `41e419bd-f3e9-43b1-8364-0ebd89fa086b` |
| kind | `delta_prefill_matrix` (DISPATCH P interleaved KV precision) |
| matrix window | `2026-08-23T19:07:29Z` → `2026-08-23T23:32:56Z` |
| derived seal | `derived/delta_prefill/sealed_41e419bd-f3e9-43b1-8364-0ebd89fa086b/` |
| sealed_utc | `2026-08-24T16:13:53.604983Z` |

### What the seal lacks

- `plan.json` has no `model_spec`, `model_specs`, or per-cell `model_spec` / `ir_sha256`.
- The derived seal `manifest.json` has no `model` block.
- Cell artifacts record `model_id: Qwen3-4B-int4-ov` and
  `diagnostics.config_path → configs/delta_n.yaml`, but not the pin path or
  `ir_sha256`.

### Git HEAD at seal wall-clock

```
5ff4e65ceed073389bd6cb05b720e7e08e6b9e0b
```

(`git rev-list -1 --before=2026-08-24T16:13:53Z HEAD` — same HEAD as at
matrix launch). That commit does **not** contain `configs/delta_n.yaml`
(the file lived only in the working tree during the run).

### Reconstruction

First commit that records the governing default:

```
e246c1a6f2cc91328ffdd797b51de8bfe22c42af  (2026-08-24 22:19:55 -0400)
```

At that commit, `configs/delta_n.yaml` declares:

```yaml
openvino:
  model_spec: configs/models/Qwen3-4B-int4-ov.yaml
```

That path is the 4B int4 pin. On-disk pin identity (unchanged; not in
`e246c1a6`, always local):

| field | value |
|---|---|
| path | `configs/models/Qwen3-4B-int4-ov.yaml` |
| `ir_sha256` | `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2` |
| revision | `b467368d16b75df14055562fe927ae8e1f15f7ef` |

Cell `model_id` values sampled from the sealed session are uniformly
`Qwen3-4B-int4-ov`, matching that pin's `name`.

**Identity for this seal is reconstructed from commit `e246c1a6` as
`configs/models/Qwen3-4B-int4-ov.yaml` (`ir_sha256` `c1821f29…`),
corroborated by cell `model_id` and by HEAD `5ff4e65` at seal time being
unable to supply the config from git alone.**

### What this does and does not affect

- **Within-matrix KV comparisons** (f16 / u8 / u4 on the same weight IR)
  are unaffected: every cell used the same weight identity.
- **Cross-run comparisons** against this seal (different weight IR, or any
  claim that needs a named `ir_sha256` from the seal itself) must cite this
  reconstruction, not the seal. The seal does not name the weight IR.

Do **not** modify the sealed tree or `plan.json`.
