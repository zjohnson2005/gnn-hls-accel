# Disaggregation: action_heavy_react_c1

**Concurrency:** 1

## GT/Intel-style headline

- CPU-side tool processing: **61.0%** of end-to-end latency
- GPU inference: **39.0%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.68% | 29,226,497 us | No |
| parse_format | 0.12% | 34,600 us | Yes |
| tokenize | 0.03% | 8,300 us | Yes |
| orchestration | 0.01% | 3,535 us | Yes |
| state_kv | 0.16% | 48,000 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 3.7%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 3.7% of hardware-amenable CPU time (after removing I/O wait) and 0.01% of normalized end-to-end cost. WARNING: coordination slice may be too small to justify silicon.
