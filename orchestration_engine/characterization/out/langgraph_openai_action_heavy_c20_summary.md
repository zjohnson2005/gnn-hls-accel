# Disaggregation: langgraph_openai_action_heavy_c20

**Concurrency:** 20

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **100.0%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **0.0%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **309,913,456 us**
- Aggregate orchestration: **65,000 us**
- Orchestration / accelerable CPU: **10.2%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.79% | 309,276,412 us | No |
| parse_format | 0.11% | 336,000 us | Yes |
| tokenize | 0.02% | 56,000 us | Yes |
| orchestration | 0.02% | 65,000 us | Yes |
| state_kv | 0.06% | 180,044 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.8%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 10.2%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 10.2% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 100.0%. At concurrency=20, aggregate coordination is 10.2% of aggregate accelerable CPU (65,000 us of 637,044 us).
