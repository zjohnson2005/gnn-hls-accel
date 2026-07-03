# Disaggregation: langgraph_action_heavy_c100

**Concurrency:** 100

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **58.9%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **41.1%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **963,813,299 us**
- Aggregate orchestration: **675,000 us**
- Orchestration / accelerable CPU: **18.3%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.62% | 960,128,299 us | No |
| parse_format | 0.17% | 1,680,000 us | Yes |
| tokenize | 0.03% | 280,000 us | Yes |
| orchestration | 0.07% | 675,000 us | Yes |
| state_kv | 0.11% | 1,050,000 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.6%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 18.3%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 18.3% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 58.9%. At concurrency=100, aggregate coordination is 18.3% of aggregate accelerable CPU (675,000 us of 3,685,000 us). Coordination is a sizeable, non-rounding-error slice.
