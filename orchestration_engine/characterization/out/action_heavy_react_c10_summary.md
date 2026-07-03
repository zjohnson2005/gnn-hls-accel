# Disaggregation: action_heavy_react_c10

**Concurrency:** 10

## GT/Intel-style headline

- CPU-side tool processing: **54.4%** of end-to-end latency
- GPU inference: **32.6%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.70% | 322,878,039 us | No |
| parse_format | 0.11% | 356,000 us | Yes |
| tokenize | 0.03% | 84,400 us | Yes |
| orchestration | 0.01% | 45,034 us | Yes |
| state_kv | 0.15% | 484,800 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 4.6%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 4.6% of hardware-amenable CPU time (after removing I/O wait) and 0.01% of normalized end-to-end cost. At concurrency=10, aggregate coordination is 4.6% of aggregate accelerable CPU cycles (45,034 us of 970,234 us). WARNING: coordination slice may be too small to justify silicon.
