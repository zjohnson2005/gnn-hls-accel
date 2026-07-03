# Disaggregation: action_heavy_react_c100

**Concurrency:** 100

## GT/Intel-style headline

- CPU-side tool processing: **47.2%** of end-to-end latency
- GPU inference: **29.3%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.66% | 3,090,097,035 us | No |
| parse_format | 0.11% | 3,510,000 us | Yes |
| tokenize | 0.03% | 837,000 us | Yes |
| orchestration | 0.04% | 1,313,488 us | Yes |
| state_kv | 0.16% | 4,824,000 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 12.5%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 12.5% of hardware-amenable CPU time (after removing I/O wait) and 0.02% of normalized end-to-end cost. At concurrency=100, aggregate coordination is 12.5% of aggregate accelerable CPU cycles (1,313,488 us of 10,484,488 us).
