# H1 EMIT-GAP — R2a 65/200 vs W-3 45/200 emission failures

Sealed trees compared (read-only):

| run | path | role |
|---|---|---|
| R2a `86d0f4cf-…` | `derived/h1_hybrid/slo_escalate_86d0f4cf-…` | H-1 local arm (`slo_escalate`) |
| W-3 `6225d6e1-…` | `derived/bfcl_feasibility/w3_weight_quality/6225d6e1-…` | weight-quality baseline |

Emission definition (matched):
- W-3: `failure_bucket == multi_turn:empty_turn_model_response` → **45/200**
- R2a: any local turn with `emitted_parseable_tool_call == false` → **65/200**
- Overlap: **all 45** W-3 empty-turn ids ⊆ R2a no-emit set; **+20** R2a-only extras.
- R2b `8ffd8371` escalated on the same **65** entries (`escalate_reason=no_parseable_tool_call`).

## Field-by-field diff

| field | W-3 `6225d6e1` | R2a `86d0f4cf` | same? |
|---|---|---|---|
| entry pin / population | W-3 multi_turn_base prefix n=200 | same pin `w3_entry_pin=3502c535…` | yes |
| model_spec | `Qwen3-4B-int4-ov.yaml` | same | yes |
| IR `ir_sha256` | `c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2` | same (via model_spec) | yes |
| placement | `gpu_only` | `gpu_only` | yes |
| residency | `RESIDENT` | `RESIDENT` | yes |
| **KV precision** | **unset / readback `dynamic`** (`enforced=false`, arm `gpu_only`) | **`u8` enforced** (arm `gpu_only_u8`) | **NO** |
| max_new_tokens | 512 | 512 | yes |
| decode | greedy `do_sample=False`, `apply_chat_template=False` | same | yes |
| step limit | `MAXIMUM_STEP_LIMIT=20` | same probe path | yes |
| prompt format | `bfcl_chat_history_tools_thinking_off` | same probe `run_multi_turn_agent_entry` | yes |
| tokenizer | HF tokenizer from model_spec | same | yes |
| scorer | multi_turn_checker + CAP-01 wrapper | same pin asserted in plan | yes |
| policy / hybrid | none (quality probe only) | `slo_escalate` (emission counted on **local** turns before cloud) | n/a for emit |

## Reading

The only material generation-config difference between the two seals is **KV cache precision**: W-3 `gpu_only` (dynamic) vs H-1 `gpu_only_u8`. Placement and residency match. That KV delta is the only measured configuration candidate that can explain a **+20/200 (+44% relative to 45)** rise in emission failure; no other listed axis moved.

This is also the R2b cost miss: predicted escalations tracked the W-3 45 empty-turn rate; measured R2b escalated **65** times on the u8 arm.

### Relation to X-2

X-2 (`x2_phase1_integrity.json`) scored trajectory **1/20 in all four** placement×residency cells. That finding is about **placement and residency**, which do **not** differ here. It does **not** speak to KV. Two separate statements:

1. This emit-gap does **not** falsify X-2's placement/residency quality-neutral claim (those axes are identical between W-3 and R2a).
2. X-2's **1/20 trajectory** resolution is coarse enough that a shift of this size (~10 pp emission) would be invisible even if KV had been in the matrix — so X-2 cannot be used to argue that arm-config changes are quality-neutral in general.

Do not treat “config is quality-neutral” as established for KV. The sealed evidence points at KV u8 vs dynamic as the plausible cause; confirming causality requires a matched re-run that varies only KV (not assumed here).

## Machine-readable companion

See `derived/h1_hybrid/emit_gap.json` (written alongside this note).
