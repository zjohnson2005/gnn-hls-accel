# Related-work search log

Search date for every section below: 2026-09-23. This file is the log required
before any "first" claim. Do not strengthen a verdict without a new dated section.

## Config-aware routing

- Claim: hardware-aware routing of local vs cloud execution.
- Date searched: 2026-09-23
- Verdict: NARROWED to a single consumer device to cloud, with static config axes.
- Allowed wording: single consumer device -> cloud with static config axes.
- Forbidden wording: "first hardware-aware routing".
- Citations: 2608.14575 (HW-Router), 2604.10907 (RouterWise), 2607.18253, 2502.11007, 2509.24050.

## Schema and context retention

- Claim: schema or context retention as a method contribution.
- Date searched: 2026-09-23
- Verdict: NARROWED to the hardware consequence (limit, TTFT, cloud $).
- Allowed wording: the hardware consequence of retention (limit, TTFT, cloud $).
- Forbidden wording: none recorded on 2026-09-23.
- Citations: 2604.21816 (Tool Attention), 2606.15508 (ToolMenuBench), 2510.00615 (ACON), "The Complexity Trap", 2608.16370 (compression costs hidden by task completion; report more than pass/fail).

## Tier penalty as a memory effect

- Claim: a tier penalty is caused by memory.
- Date searched: 2026-09-23
- Verdict: SURVIVES as a measured platform-dependent number only.
- Allowed wording: a measured platform-dependent number.
- Forbidden wording: "we discover memory causes".
- Citations: none recorded on 2026-09-23.

## Phase split on unified memory

- Claim: novelty for splitting prefill and decode across devices on unified memory.
- Date searched: 2026-09-23
- Verdict: DEAD as a novelty claim. AMD Lemonade ships NPU prefill + iGPU decode. HET-1 stays as a measurement of Intel handoff cost.
- Allowed wording: HET-1 measures Intel handoff cost.
- Forbidden wording: phase split on unified memory as a novelty claim.
- Citations: AMD Lemonade (NPU prefill + iGPU decode). No paper id recorded on 2026-09-23.

## Competitors to cite

- Claim: on-device and AI-PC agent characterization.
- Date searched: 2026-09-23
- Verdict: CITE. Not a novelty claim.
- Allowed wording: cite these systems for what they measured.
- Forbidden wording: "first characterization of on-device agents".
- Citations: 2605.10380 Agent-X; 2608.25053 Hydra (1k-5k inputs, roughly linear TTFT); 2603.23640; 2508.06753 (AI-PC hybrid).

## Mechanism references

- Claim: mechanism citations for allocation, GPU memory, speculative decoding, and NPU failure modes.
- Date searched: 2026-09-23
- Verdict: RECORDED.
- Allowed wording: cite the issue or paper for the mechanism it names.
- Forbidden wording: none recorded on 2026-09-23.
- Citations: OpenVINO #37501 (logits buffer alloc); Intel Shared GPU Memory Override; 2503.03777 FlexInfer; OpenVINO discussion #36484 (NPU/CPU draft speculative decoding); openvino.genai #3255 (NPU garbage past prompt limit); openvino.genai #4367 (CB prefix-cache greedy divergence); openvino #35641 (NPU int8 crash).

## Q-1 anomaly

- Claim: published Qwen3-4B 35.25% and Qwen3-8B 34% on multi_turn_base.
- Date searched: 2026-09-23
- Verdict: TO CONFIRM. Source URL not yet recorded.
- Allowed wording: quote 35.25% and 34% only with this TO CONFIRM mark until the URL is recorded.
- Forbidden wording: citing those percentages as a confirmed published source.
- Citations: source URL NOT YET RECORDED.
