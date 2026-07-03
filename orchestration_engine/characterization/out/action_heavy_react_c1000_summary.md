# Disaggregation: action_heavy_react_c1000

**Concurrency:** 1000

## GT/Intel-style headline

- CPU-side tool processing: **29.3%** of end-to-end latency
- GPU inference: **18.0%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.55% | 31,257,056,078 us | No |
| parse_format | 0.11% | 35,122,500 us | Yes |
| tokenize | 0.03% | 8,373,150 us | Yes |
| orchestration | 0.16% | 50,992,778 us | Yes |
| state_kv | 0.15% | 48,250,800 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.5%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.1%** of E2E
- **Orchestration: 35.7%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 35.7% of hardware-amenable CPU time (after removing I/O wait) and 0.05% of normalized end-to-end cost. At concurrency=1000, aggregate coordination is 35.7% of aggregate accelerable CPU cycles (50,992,778 us of 142,739,228 us). Coordination is a sizeable, non-rounding-error slice.
