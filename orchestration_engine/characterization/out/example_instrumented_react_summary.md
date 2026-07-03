# Disaggregation: example_instrumented_react

**Concurrency:** 1

## GT/Intel-style headline

- CPU-side tool processing: **46.6%** of end-to-end latency
- GPU inference: **53.4%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | µs | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.74% | 2,000,000 us | No |
| parse_format | 0.12% | 2,500 us | Yes |
| tokenize | 0.02% | 400 us | Yes |
| orchestration | 0.01% | 150 us | Yes |
| state_kv | 0.11% | 2,200 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.1%** of E2E
- **Orchestration: 2.9%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 2.9% of hardware-amenable CPU time (after removing I/O wait) and 0.00% of normalized end-to-end cost. WARNING: coordination slice may be too small to justify silicon.
