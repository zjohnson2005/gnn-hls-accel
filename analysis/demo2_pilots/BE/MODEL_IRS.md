# Model IRs for arm P (Task BE, 2026-10-21 ET; Mac, Hub metadata only, nothing downloaded)

All three requested IRs exist as official OpenVINO Hugging Face repos. Pinned at their current
main revision (HF API, 2026-10-21). Files read: config.json, openvino_config.json,
openvino_model.xml (rt_info), README.md, chat_template.jinja.

| repo @ revision | rt_info weight_compression | openvino_config dataset | card | base_model | positions / rope |
|---|---|---|---|---|---|
| OpenVINO/Qwen3-8B-int4-ov @ 5c47abf4b8e12ebe8e99745bb0c1ec17e0c0abcc | int4_asym, group 128, ratio 1.0, AWQ False, scale_estimation True, backup int8_asym | wikitext2 | INT4_ASYM, SE, wikitext2 | Qwen/Qwen3-8B | 40,960 / none |
| OpenVINO/Qwen3-8B-int8-ov @ f82c978d714abc9c398efa361827a76d3cae5473 | int8_asym, group -1 (per-channel), AWQ False, SE False | null | INT8_ASYM | Qwen/Qwen3-8B | 40,960 / none |
| OpenVINO/Qwen3-4B-int8-ov @ fd9c3cc8adf942151e48904b7341a57eae58d8d5 | int8_asym, group -1, AWQ False, SE False | null | INT8_ASYM | Qwen/Qwen3-4B | 40,960 / none |
| (arm A, for reference) OpenVINO/Qwen3-4B-int4-ov @ b467368d | int4_sym, group 128, AWQ True, SE False | null | AWQ + SE + wikitext2 (card disagrees) | Qwen/Qwen3-4B | 40,960 / none |

- All are the hybrid Qwen3, not 2507: base_model is Qwen/Qwen3-8B or Qwen3-4B, and the chat
  template has the enable_thinking switch.
- 8B: 36 layers, 8 KV heads, head_dim 128, hidden 4,096. 4B: 36 / 8 / 128 / 2,560.
- The KV cache per token is the same for 4B and 8B (DERIVED: same layers, KV heads and
  head_dim).
- chat_template.jinja, tokenizer.json and tokenizer_config.json are byte-identical across all
  four pins (sha256 a55ee1b1..., aeb13307..., 443bfa62...), so rendered prompts have the same
  token counts.
- The 8B INT4 card and rt_info agree. The INT8 IRs are data-free.
- No 8B IR with the 4B INT4 recipe (INT4_SYM + AWQ) is published. That difference is part of
  arm P's "device-provisioned" label.

Pins:
- configs/models/Qwen3-8B-int4-ov.v2.yaml and configs/models/Qwen3-4B-int8-ov.yaml already
  existed at these revisions. tools/pin_model_from_hub.py reproduces their ir_sha256 from Hub
  metadata alone (cd97874b..., f7d323d0...).
- configs/models/Qwen3-8B-int8-ov.yaml is new, built the same way: ir_sha256
  eac56228f6e04bd59fed2135d09b26c09953f8f3941e20c60d637fb563e526a3, 8,224,022,312 bytes.
- The host download (seam.tools.fetch_model) must reproduce each pin's ir_sha256, or the
  download script stops.
