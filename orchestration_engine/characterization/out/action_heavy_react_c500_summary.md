# Disaggregation: action_heavy_react_c500

**Concurrency:** 500

## GT/Intel-style headline

- CPU-side tool processing: **36.7%** of end-to-end latency
- GPU inference: **22.5%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.58% | 15,641,710,154 us | No |
| parse_format | 0.11% | 17,582,500 us | Yes |
| tokenize | 0.03% | 4,189,550 us | Yes |
| orchestration | 0.13% | 20,380,118 us | Yes |
| state_kv | 0.15% | 24,135,600 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.6%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 30.7%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 30.7% of hardware-amenable CPU time (after removing I/O wait) and 0.05% of normalized end-to-end cost. At concurrency=500, aggregate coordination is 30.7% of aggregate accelerable CPU cycles (20,380,118 us of 66,287,768 us). Coordination is a sizeable, non-rounding-error slice.
