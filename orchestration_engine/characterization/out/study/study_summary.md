# LangGraph Phase 1 study

Labels:
- **OpenAI trace**: real wall-clock LLM API latency
- **Calibrated mock**: mock LangGraph structure, timings from wall-clock calibration

| Workload | Concurrency | CPU tool / E2E | I/O wait / CPU tool | Orch / CPU tool | Orch / (CPU-IO) | Orch / E2E (per-agent) |
|----------|-------------|----------------|---------------------|-----------------|------------------|------------|
| langgraph_action_heavy_calibrated_c1 | 1 | 64.2% | 99.7% | 0.032% | 10.2% | 0.02% |
| langgraph_action_heavy_calibrated_c100 | 100 | 64.5% | 99.7% | 0.068% | 19.7% | 0.04% |
| langgraph_action_heavy_calibrated_c500 | 500 | 64.5% | 99.5% | 0.217% | 44.0% | 0.14% |
| langgraph_reasoning_heavy_calibrated_c1 | 1 | 3.7% | 97.2% | 0.280% | 9.8% | 0.01% |
| langgraph_reasoning_heavy_calibrated_c100 | 100 | 3.7% | 96.8% | 0.628% | 19.5% | 0.02% |
| langgraph_reasoning_heavy_calibrated_c500 | 500 | 3.7% | 95.4% | 2.010% | 44.0% | 0.07% |

# Disaggregation: langgraph_action_heavy_calibrated_c1

**Concurrency:** 1

## GT/Intel-style headline

- CPU-side tool processing: **64.2%** of end-to-end latency
- GPU inference (per-agent equiv.): **35.8%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.69% | 10,325,859 us | No |
| parse_format | 0.16% | 16,800 us | Yes |
| tokenize | 0.01% | 1,596 us | Yes |
| orchestration | 0.03% | 3,279 us | Yes |
| state_kv | 0.10% | 10,507 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 10.2%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 10.2% of hardware-amenable CPU time (after removing I/O wait). Per-agent orchestration is 0.02% of E2E.


---

# Disaggregation: langgraph_action_heavy_calibrated_c100

**Concurrency:** 100

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **64.5%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **35.5%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **1,047,170,125 us**
- Aggregate orchestration: **710,100 us**
- Orchestration / accelerable CPU: **19.7%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.66% | 1,043,569,725 us | No |
| parse_format | 0.16% | 1,680,000 us | Yes |
| tokenize | 0.01% | 159,600 us | Yes |
| orchestration | 0.07% | 710,100 us | Yes |
| state_kv | 0.10% | 1,050,700 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.7%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 19.7%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 19.7% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 64.5%. At concurrency=100, aggregate coordination is 19.7% of aggregate accelerable CPU (710,100 us of 3,600,400 us). Coordination is a sizeable, non-rounding-error slice.


---

# Disaggregation: langgraph_action_heavy_calibrated_c500

**Concurrency:** 500

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **64.5%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **35.5%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **5,241,160,585 us**
- Aggregate orchestration: **11,350,500 us**
- Orchestration / accelerable CPU: **44.0%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 99.51% | 5,215,358,585 us | No |
| parse_format | 0.16% | 8,400,000 us | Yes |
| tokenize | 0.01% | 798,000 us | Yes |
| orchestration | 0.22% | 11,350,500 us | Yes |
| state_kv | 0.10% | 5,253,500 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **99.5%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.3%** of E2E
- **Orchestration: 44.0%** of hardware-amenable CPU
- Orchestration: **0.1%** of E2E

## Headline

Coordination is 44.0% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 64.5%. At concurrency=500, aggregate coordination is 44.0% of aggregate accelerable CPU (11,350,500 us of 25,802,000 us). Coordination is a sizeable, non-rounding-error slice.


---

# Disaggregation: langgraph_reasoning_heavy_calibrated_c1

**Concurrency:** 1

## GT/Intel-style headline

- CPU-side tool processing: **3.7%** of end-to-end latency
- GPU inference (per-agent equiv.): **96.3%** of E2E

## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 97.15% | 751,193 us | No |
| parse_format | 1.45% | 11,200 us | Yes |
| tokenize | 0.15% | 1,140 us | Yes |
| orchestration | 0.28% | 2,163 us | Yes |
| state_kv | 0.97% | 7,500 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **97.2%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.1%** of E2E
- **Orchestration: 9.8%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 9.8% of hardware-amenable CPU time (after removing I/O wait). Per-agent orchestration is 0.01% of E2E.


---

# Disaggregation: langgraph_reasoning_heavy_calibrated_c100

**Concurrency:** 100

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **3.7%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **96.3%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **76,633,145 us**
- Aggregate orchestration: **480,900 us**
- Orchestration / accelerable CPU: **19.5%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 96.78% | 74,168,245 us | No |
| parse_format | 1.46% | 1,120,000 us | Yes |
| tokenize | 0.15% | 114,000 us | Yes |
| orchestration | 0.63% | 480,900 us | Yes |
| state_kv | 0.98% | 750,000 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **96.8%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.1%** of E2E
- **Orchestration: 19.5%** of hardware-amenable CPU
- Orchestration: **0.0%** of E2E

## Headline

Coordination is 19.5% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 3.7%. At concurrency=100, aggregate coordination is 19.5% of aggregate accelerable CPU (480,900 us of 2,464,900 us). Coordination is a sizeable, non-rounding-error slice.


---

# Disaggregation: langgraph_reasoning_heavy_calibrated_c500

**Concurrency:** 500

## GT/Intel-style headline

- Per-agent-equivalent CPU tool / E2E: **3.7%** (use this for GT comparison, not wall-clock batch time)
- GPU inference (per-agent equiv.): **96.3%** of E2E

## Datacenter aggregate

- Aggregate CPU tool time: **388,300,698 us**
- Aggregate orchestration: **7,804,500 us**
- Orchestration / accelerable CPU: **44.0%**


## CPU tool-phase breakdown (% of CPU tool time)

| Slice | % of CPU tool | us | Accelerable? |
|-------|---------------|-----|--------------|
| io_wait | 95.44% | 370,576,198 us | No |
| parse_format | 1.44% | 5,600,000 us | Yes |
| tokenize | 0.15% | 570,000 us | Yes |
| orchestration | 2.01% | 7,804,500 us | Yes |
| state_kv | 0.97% | 3,750,000 us | Partly |
| other | 0.00% | 0 us | Yes |

## Key numbers (the publishable floor)

- I/O wait (unaccelerable): **95.4%** of CPU tool phase
- Hardware-amenable CPU (CPU tool - I/O): **0.2%** of E2E
- **Orchestration: 44.0%** of hardware-amenable CPU
- Orchestration: **0.1%** of E2E

## Headline

Coordination is 44.0% of hardware-amenable CPU time (after removing I/O wait). Per-agent-equivalent CPU tool / E2E is 3.7%. At concurrency=500, aggregate coordination is 44.0% of aggregate accelerable CPU (7,804,500 us of 17,724,500 us). Coordination is a sizeable, non-rounding-error slice.


---
