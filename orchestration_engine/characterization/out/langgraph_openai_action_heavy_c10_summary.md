# Disaggregation: langgraph_openai_action_heavy_c10

**Concurrency:** 10

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **100.0%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **0.0%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **156,664,903 us**
- Aggregate orchestration: **32,500 us**
- Orchestration / accelerable CPU: **10.2%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.80% | 156,346,381 us | No |
| parse_format | 0.11% | 168,000 us | Yes |
| tokenize | 0.02% | 28,000 us | Yes |
| orchestration | 0.02% | 32,500 us | Yes |
| state_kv | 0.06% | 90,022 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.8%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 10.2%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 10.2% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 100.0%. At concurrency=10, aggregate coordination is 10.2% of aggregate accelerable CPU (32,500 us of 318,522 us).
