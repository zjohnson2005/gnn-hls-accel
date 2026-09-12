# Phase 0 Inventory — Agent Trace Artifacts

Repo root: `C:\Users\zjohn\Projects\gnn-hls-accel`

Primary out dir: `C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out`



## 1. TurnTrace — trajectory_records.jsonl

Found **9** trajectory_records.jsonl files.

### `apu_characterization\out\turntrace_v2\_gate_smoke\replay\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 3
- distinct_sessions/trajectories: 3
- turns_per_trajectory (n_turns field): min=6 median=6.0 max=6
- schema:
  - `arm`: str
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `interventions_active`: list[empty] len=0
  - `joules_total`: NoneType
  - `n_turns`: int
  - `pair_id`: str
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `usd_model_cost`: float
  - `workload_id`: str
### sample[0]
```json
{
  "arm": "baseline_naive",
  "cache_mode": "cache-disabled",
  "deployment_id": "L1b",
  "harness_id": "raw_python",
  "interventions_active": [],
  "joules_total": null,
  "n_turns": 6,
  "pair_id": "",
  "replay_bundle_path": "apu_characterization/out/turntrace_v2/_gate_smoke/replay/bundles/syn-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 444.1560111998797,
  "trajectory_id": "syn-000",
  "usd_model_cost": 0.0,
  "workload_id": "swebench_lite_synthetic"
}
```

### sample[1]
```json
{
  "arm": "baseline_naive",
  "cache_mode": "cache-disabled",
  "deployment_id": "L1b",
  "harness_id": "raw_python",
  "interventions_active": [],
  "joules_total": null,
  "n_turns": 6,
  "pair_id": "",
  "replay_bundle_path": "apu_characterization/out/turntrace_v2/_gate_smoke/replay/bundles/syn-001.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 444.1560111998797,
  "trajectory_id": "syn-001",
  "usd_model_cost": 0.0,
  "workload_id": "swebench_lite_synthetic"
}
```

### sample[2]
```json
{
  "arm": "baseline_naive",
  "cache_mode": "cache-disabled",
  "deployment_id": "L1b",
  "harness_id": "raw_python",
  "interventions_active": [],
  "joules_total": null,
  "n_turns": 6,
  "pair_id": "",
  "replay_bundle_path": "apu_characterization/out/turntrace_v2/_gate_smoke/replay/bundles/syn-002.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 444.1560111998797,
  "trajectory_id": "syn-002",
  "usd_model_cost": 0.0,
  "workload_id": "swebench_lite_synthetic"
}
```

### `apu_characterization\out\turntrace_v2\cloud_c1_mock\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 4
- distinct_sessions/trajectories: 4
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_c1_mock\\bundles\\C1-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5152.205944061279,
  "trajectory_id": "C1-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[1]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "langgraph",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_c1_mock\\bundles\\C1-langgraph-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5154.205799102783,
  "trajectory_id": "C1-langgraph-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[2]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_c1_mock\\bundles\\C1-raw_python-001.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5152.205944061279,
  "trajectory_id": "C1-raw_python-001",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_a\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 2
- distinct_sessions/trajectories: 2
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C1\\phase_a\\bundles\\C1-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 3870.370388031006,
  "trajectory_id": "C1-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[1]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "langgraph",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C1\\phase_a\\bundles\\C1-langgraph-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 6237.2918128967285,
  "trajectory_id": "C1-langgraph-000",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_b\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 18
- distinct_sessions/trajectories: 18
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C1\\phase_b\\bundles\\C1-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4117.749929428101,
  "trajectory_id": "C1-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[1]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "langgraph",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C1\\phase_b\\bundles\\C1-langgraph-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5178.712606430054,
  "trajectory_id": "C1-langgraph-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[2]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C1\\phase_b\\bundles\\C1-raw_python-001.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5571.310997009277,
  "trajectory_id": "C1-raw_python-001",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_a\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 2
- distinct_sessions/trajectories: 2
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C2\\phase_a\\bundles\\C2-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5498.896360397339,
  "trajectory_id": "C2-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[1]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "langgraph",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C2\\phase_a\\bundles\\C2-langgraph-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4831.3307762146,
  "trajectory_id": "C2-langgraph-000",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_b\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 18
- distinct_sessions/trajectories: 18
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C2\\phase_b\\bundles\\C2-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4968.230485916138,
  "trajectory_id": "C2-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[1]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "langgraph",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C2\\phase_b\\bundles\\C2-langgraph-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4946.704864501953,
  "trajectory_id": "C2-langgraph-000",
  "workload_id": "swebench_lite_layer1"
}
```

### sample[2]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_full\\cell_C2\\phase_b\\bundles\\C2-raw_python-001.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4572.70359992981,
  "trajectory_id": "C2-raw_python-001",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C1\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 1
- distinct_sessions/trajectories: 1
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C1",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_smoke\\smoke_C1\\bundles\\C1-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 4015.7270431518555,
  "trajectory_id": "C1-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C2\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 1
- distinct_sessions/trajectories: 1
- turns_per_trajectory (n_turns field): min=4 median=4.0 max=4
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "provider_default",
  "deployment_id": "C2",
  "harness_id": "raw_python",
  "n_turns": 4,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cloud_smoke\\smoke_C2\\bundles\\C2-raw_python-000.ttbundle",
  "success_metric": "swebench_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 5779.759883880615,
  "trajectory_id": "C2-raw_python-000",
  "workload_id": "swebench_lite_layer1"
}
```

### `apu_characterization\out\turntrace_v2\cpu_dryrun\corpus\trajectory_records.jsonl`
- format: JSONL
- record_count: 5
- distinct_sessions/trajectories: 5
- turns_per_trajectory (n_turns field): min=6 median=6.0 max=6
- schema:
  - `cache_mode`: str
  - `deployment_id`: str
  - `harness_id`: str
  - `n_turns`: int
  - `replay_bundle_path`: str
  - `success_metric`: str
  - `task_success`: bool
  - `total_cost_usd`: float
  - `total_energy_j`: NoneType
  - `total_wall_clock_ms`: float
  - `trajectory_id`: str
  - `workload_id`: str
### sample[0]
```json
{
  "cache_mode": "cache-disabled",
  "deployment_id": "CPU0",
  "harness_id": "raw_python",
  "n_turns": 6,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cpu_dryrun\\bundles\\cpu-dryrun-000.ttbundle",
  "success_metric": "toy_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 10865.149974822998,
  "trajectory_id": "cpu-dryrun-000",
  "workload_id": "toy_agent_cpu_dryrun"
}
```

### sample[1]
```json
{
  "cache_mode": "cache-disabled",
  "deployment_id": "CPU0",
  "harness_id": "raw_python",
  "n_turns": 6,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cpu_dryrun\\bundles\\cpu-dryrun-001.ttbundle",
  "success_metric": "toy_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 10634.017944335938,
  "trajectory_id": "cpu-dryrun-001",
  "workload_id": "toy_agent_cpu_dryrun"
}
```

### sample[2]
```json
{
  "cache_mode": "cache-disabled",
  "deployment_id": "CPU0",
  "harness_id": "raw_python",
  "n_turns": 6,
  "replay_bundle_path": "apu_characterization\\out\\turntrace_v2\\cpu_dryrun\\bundles\\cpu-dryrun-002.ttbundle",
  "success_metric": "toy_pass",
  "task_success": true,
  "total_cost_usd": 0.0,
  "total_energy_j": null,
  "total_wall_clock_ms": 10838.172912597656,
  "trajectory_id": "cpu-dryrun-002",
  "workload_id": "toy_agent_cpu_dryrun"
}
```



## 1b. TurnTrace — .ttbundle archives

Found **133** `.ttbundle` files.

Counts by top-level area:
- `_gate_smoke`: 3
- `cloud_c1_mock`: 4
- `cloud_full`: 76
- `cloud_smoke`: 2
- `cpu_dryrun`: 6
- `rev_c_cp2`: 42

### Bundle inspect: `apu_characterization\out\turntrace_v2\rev_c_cp2\class_i\bundles\CPU0-langgraph-TT-EDIT-s0-append_layout-baseline_naive.ttbundle` (size=143780)
- unreadable: 'utf-8' codec can't decode byte 0xda in position 1: invalid continuation byte

### Bundle inspect: `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\bundles_all\C1-langgraph-000.ttbundle` (size=1089)
- unreadable: 'utf-8' codec can't decode byte 0xda in position 1: invalid continuation byte

### Bundle inspect: `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\bundles_all\C2-langgraph-000.ttbundle` (size=1197)
- unreadable: 'utf-8' codec can't decode byte 0xda in position 1: invalid continuation byte

### Bundle inspect: `apu_characterization\out\turntrace_v2\_gate_smoke\replay\bundles\syn-000.ttbundle` (size=881)
- unreadable: 'utf-8' codec can't decode byte 0xda in position 1: invalid continuation byte


## 1c. TurnTrace — *.events.json

Found **93** events.json files.

- size bytes: min=6358 median=27304.0 max=1013698

### `apu_characterization\out\turntrace_v2\cloud_c1_mock\trajectories\C1-langgraph-000.events.json`
- format: JSON list
- record_count: 4
- schema[0]:
  - `assembled_context`: str
  - `cache_state`: str
  - `call_site_tag`: NoneType
  - `deployment_id`: str
  - `energy_j`: NoneType
  - `engine`: str
  - `engine_token_ids`: list[int] len=16
  - `engine_tokens_in`: int
  - `engine_version`: str
  - `expected_horizon`: int
  - `extra`: dict
  - `graph_node`: str
  - `harness_id`: str
  - `model_id`: str
  - `network_method`: str
  - `pred_decode_tokens`: NoneType
  - `prefill_method`: str
  - `prefix_hit_tokens`: int
  - `prior_semantic_token_ids`: NoneType
  - `quantization`: str
  - `raw_model_output`: str
  - `reasoning_mode`: str
  - `requested_tokens_in`: int
  - `status`: str
  - `t_decode_ms`: float
  - `t_network_ms`: float
  - `t_orch_post_ms`: float
  - `t_orch_pre_ms`: float
  - `t_prefill_ms`: float
  - `tokenizer_id`: str
  - `tokens_out`: int
  - `tool_names`: list[str] len=2
  - `trajectory_id`: str
  - `turn_index`: int
  - `wall_clock_end`: float
  - `wall_clock_start`: float
### sample[0]
```json
{
  "trajectory_id": "C1-langgraph-000",
  "turn_index": 0,
  "harness_id": "langgraph",
  "deployment_id": "C1",
  "assembled_context": "system: You are a coding agent. Use tools to fix the bug.\nuser: Fix bug 0 in module.",
  "raw_model_output": "ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok",
  "tool_names": [
    "read_file",
    "grep"
  ],
  "graph_node": "agent",
  "call_site_tag": null,
  "status": "ok",
  "t_orch_pre_ms": 1.2,
  "t_orch_post_ms": 1.8,
  "t_network_ms": 5.0,
  "network_method": "estimated:probe_median",
  "t_prefill_ms": 0.53200256,
  "prefill_method": "ttft_derived",
  "t_decode_ms": 1280.0,
  "engine_tokens_in": 16,
  "requested_tokens_in": 16,
  "engine_token_ids": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15
  ],
  "tokens_out": 64,
  "cache_state": "disabled",
  "prefix_hit_tokens": 0,
  "model_id": "gpt-4.1-mini",
  "quantization": "api",
  "reasoning_mode": "off",
  "engine": "openai_compat",
  "engine_version": "1",
  "wall_clock_start": 1784211822.4432294,
  "wall_clock_end": 1784211823.7317615,
  "energy_j": null,
  "tokenizer_id": "mock",
  "expected_horizon": 4,
  "pred_decode_tokens": null,
  "prior_semantic_token_ids": null,
  "extra": {}
}
```

### sample[1]
```json
{
  "trajectory_id": "C1-langgraph-000",
  "turn_index": 1,
  "harness_id": "langgraph",
  "deployment_id": "C1",
  "assembled_context": "system: You are a coding agent. Use tools to fix the bug.\nuser: Fix bug 0 in module.\nassistant: tool_call read_file\ntool: {'path': 'main.py'}",
  "raw_model_output": "ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok",
  "tool_names": [
    "edit_file"
  ],
  "graph_node": "tools",
  "call_site_tag": null,
  "status": "ok",
  "t_orch_pre_ms": 1.2,
  "t_orch_post_ms": 1.8,
  "t_network_ms": 5.0,
  "network_method": "estimated:probe_median",
  "t_prefill_ms": 0.540004,
  "prefill_method": "ttft_derived",
  "t_decode_ms": 1280.0,
  "engine_tokens_in": 20,
  "requested_tokens_in": 20,
  "engine_token_ids": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19
  ],
  "tokens_out": 64,
  "cache_state": "disabled",
  "prefix_hit_tokens": 0,
  "model_id": "gpt-4.1-mini",
  "quantization": "api",
  "reasoning_mode": "off",
  "engine": "openai_compat",
  "engine_version": "1",
  "wall_clock_start": 1784211822.4436247,
  "wall_clock_end": 1784211823.7321646,
  "energy_j": null,
  "tokenizer_id": "mock",
  "expected_horizon": 4,
  "pred_decode_tokens": null,
  "prior_semantic_token_ids": null,
  "extra": {}
}
```

### sample[2]
```json
{
  "trajectory_id": "C1-langgraph-000",
  "turn_index": 2,
  "harness_id": "langgraph",
  "deployment_id": "C1",
  "assembled_context": "system: You are a coding agent. Use tools to fix the bug.\nuser: Fix bug 0 in module.\nassistant: tool_call read_file\ntool: {'path': 'main.py'}\nassistant: tool_call edit_file\ntool: {'path': 'main.py', 'content': 'def add(a, b):\\n    return a + b\\n'}",
  "raw_model_output": "ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok ok",
  "tool_names": [
    "run_tests"
  ],
  "graph_node": "agent",
  "call_site_tag": null,
  "status": "ok",
  "t_orch_pre_ms": 1.2,
  "t_orch_post_ms": 1.8,
  "t_network_ms": 5.0,
  "network_method": "estimated:probe_median",
  "t_prefill_ms": 0.56401024,
  "prefill_method": "ttft_derived",
  "t_decode_ms": 1280.0,
  "engine_tokens_in": 32,
  "requested_tokens_in": 32,
  "engine_token_ids": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31
  ],
  "tokens_out": 64,
  "cache_state": "disabled",
  "prefix_hit_tokens": 0,
  "model_id": "gpt-4.1-mini",
  "quantization": "api",
  "reasoning_mode": "off",
  "engine": "openai_compat",
  "engine_version": "1",
  "wall_clock_start": 1784211822.44372,
  "wall_clock_end": 1784211823.732284,
  "energy_j": null,
  "tokenizer_id": "mock",
  "expected_horizon": 4,
  "pred_decode_tokens": null,
  "prior_semantic_token_ids": null,
  "extra": {}
}
```


## 2. OA-01 — turn_records.jsonl / trajectory_record.json

Found **18** OA01 run directories under `out/oa01/runs/`.

- turn_records.jsonl files: 17
- trajectory_record.json files: 17

### Aggregate over all OA-01 turn_records.jsonl
- format: JSONL (one turn per line)
- total_turn_records: 335
- distinct_trajectories (from field or dirname): 17
- turns_per_trajectory: min=3 median=15.0 max=51
- schema:
  - `actually_recomputed_redundant_tokens`: int
  - `api_attempt_count`: int
  - `api_call_ids`: list[str] len=1
  - `audit_flags`: list[str] len=1
  - `call_id`: str
  - `fanout_siblings`: int
  - `input_tokens`: int
  - `interval_end_unix_ns`: int
  - `interval_start_unix_ns`: int
  - `is_tool_call`: bool
  - `local_lcp_tokens`: int
  - `local_serialized_tokens`: int
  - `loop_membership`: bool
  - `necessary_prefill_tokens`: int
  - `output_tokens`: int
  - `provider_recovered_tokens`: int
  - `repeat_count`: int
  - `status`: str
  - `step_type_semantic`: str
  - `structurally_redundant_tokens`: int
  - `t_decode_ms`: NoneType
  - `t_model_observed_ms`: float
  - `t_network_ms`: NoneType
  - `t_orch_gap_ms`: float
  - `t_prefill_ms`: NoneType
  - `t_tool_ms`: float
  - `t_turn_wall_ms`: float
  - `task_id`: str
  - `template_overhead_envelope_tokens`: int
  - `timing_method`: str
  - `tool_names`: list[str] len=4
  - `trajectory_id`: str
  - `turn_index`: int
### sample[0]
```json
{
  "actually_recomputed_redundant_tokens": 0,
  "api_attempt_count": 1,
  "api_call_ids": [
    "OA01-M-03-pydata__xarray-3364-call-0000-5fda6ada"
  ],
  "audit_flags": [
    "prefill_decode_network_not_isolated"
  ],
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0000-5fda6ada",
  "fanout_siblings": 3,
  "input_tokens": 1166,
  "interval_end_unix_ns": 1784225795551059542,
  "interval_start_unix_ns": 1784225753329552529,
  "is_tool_call": true,
  "local_lcp_tokens": 0,
  "local_serialized_tokens": 1273,
  "loop_membership": false,
  "necessary_prefill_tokens": 1166,
  "output_tokens": 382,
  "provider_recovered_tokens": 0,
  "repeat_count": 1,
  "status": "ok",
  "step_type_semantic": "inspect+inspect+inspect+inspect",
  "structurally_redundant_tokens": 0,
  "t_decode_ms": null,
  "t_model_observed_ms": 7511.292057,
  "t_network_ms": null,
  "t_orch_gap_ms": 33704.549365,
  "t_prefill_ms": null,
  "t_tool_ms": 1005.665591,
  "t_turn_wall_ms": 42221.507013,
  "task_id": "pydata__xarray-3364",
  "template_overhead_envelope_tokens": 256,
  "timing_method": "nonstreaming_first_byte_includes_decode",
  "tool_names": [
    "bash",
    "bash",
    "bash",
    "bash"
  ],
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "turn_index": 0
}
```

### sample[1]
```json
{
  "actually_recomputed_redundant_tokens": 0,
  "api_attempt_count": 1,
  "api_call_ids": [
    "OA01-M-03-pydata__xarray-3364-call-0001-a856003b"
  ],
  "audit_flags": [
    "prefill_decode_network_not_isolated"
  ],
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0001-a856003b",
  "fanout_siblings": 0,
  "input_tokens": 5598,
  "interval_end_unix_ns": 1784225804111767213,
  "interval_start_unix_ns": 1784225795551059542,
  "is_tool_call": true,
  "local_lcp_tokens": 1271,
  "local_serialized_tokens": 5950,
  "loop_membership": false,
  "necessary_prefill_tokens": 4327,
  "output_tokens": 240,
  "provider_recovered_tokens": 1408,
  "repeat_count": 1,
  "status": "ok",
  "step_type_semantic": "inspect",
  "structurally_redundant_tokens": 1271,
  "t_decode_ms": null,
  "t_model_observed_ms": 8132.197119,
  "t_network_ms": null,
  "t_orch_gap_ms": 188.05397099999936,
  "t_prefill_ms": null,
  "t_tool_ms": 240.456581,
  "t_turn_wall_ms": 8560.707671,
  "task_id": "pydata__xarray-3364",
  "template_overhead_envelope_tokens": 256,
  "timing_method": "nonstreaming_first_byte_includes_decode",
  "tool_names": [
    "bash"
  ],
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "turn_index": 1
}
```

### sample[2]
```json
{
  "actually_recomputed_redundant_tokens": 188,
  "api_attempt_count": 1,
  "api_call_ids": [
    "OA01-M-03-pydata__xarray-3364-call-0002-f3b810e4"
  ],
  "audit_flags": [
    "prefill_decode_network_not_isolated"
  ],
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0002-f3b810e4",
  "fanout_siblings": 2,
  "input_tokens": 6327,
  "interval_end_unix_ns": 1784225815583940080,
  "interval_start_unix_ns": 1784225804111767213,
  "is_tool_call": true,
  "local_lcp_tokens": 5948,
  "local_serialized_tokens": 6808,
  "loop_membership": false,
  "necessary_prefill_tokens": 379,
  "output_tokens": 382,
  "provider_recovered_tokens": 5760,
  "repeat_count": 1,
  "status": "ok",
  "step_type_semantic": "inspect+inspect+inspect",
  "structurally_redundant_tokens": 5948,
  "t_decode_ms": null,
  "t_model_observed_ms": 10317.560168,
  "t_network_ms": null,
  "t_orch_gap_ms": 568.6991419999995,
  "t_prefill_ms": null,
  "t_tool_ms": 585.913557,
  "t_turn_wall_ms": 11472.172867,
  "task_id": "pydata__xarray-3364",
  "template_overhead_envelope_tokens": 256,
  "timing_method": "nonstreaming_first_byte_includes_decode",
  "tool_names": [
    "bash",
    "bash",
    "bash"
  ],
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "turn_index": 2
}
```

### Example trajectory_record.json: `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\trajectory_record.json`
- schema:
  - `censor_reason`: NoneType
  - `censored`: bool
  - `cost_anomaly`: bool
  - `cost_usd`: float
  - `exit_status`: str
  - `flags`: list[str] len=1
  - `model_id`: str
  - `outcome`: str
  - `phase`: str
  - `replay_bundle_path`: str
  - `subject_trajectory_path`: str
  - `success`: bool
  - `task_id`: str
  - `trajectory_id`: str
  - `turns`: int
  - `wall_clock_ms`: float
```json
{
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "task_id": "pydata__xarray-3364",
  "phase": "M",
  "model_id": "openai/gpt-4.1",
  "outcome": "failure",
  "success": false,
  "censored": false,
  "censor_reason": null,
  "turns": 28,
  "wall_clock_ms": 562124.946385,
  "cost_usd": 0.210706,
  "cost_anomaly": false,
  "exit_status": "Submitted",
  "subject_trajectory_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-03-pydata__xarray-3364/subject/pydata__xarray-3364/pydata__xarray-3364.traj.json",
  "replay_bundle_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-03-pydata__xarray-3364/replay/OA01-M-03-pydata__xarray-3364.oa01bundle",
  "flags": [
    "nonstreaming_subject_default"
  ]
}
```

### OA-01 raw/boundary/exec jsonl candidates: 67
- `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\derived\exec_spans.jsonl` lines≈36 size=35415
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-b50a6a19",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pydata_1776_xarray-3364:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 281.479462,
  "end_unix_ns": 1784225783075835559,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-9036340160ef482c962971b9ed85b8f9",
  "start_unix_ns": 1784225782794356097,
  "timed_out": false,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
    "bash",
    "-c",
    "ls -l"
  ],
  "command": "bash\u0000-c\u0000ls -l",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "docker_operation": "exec",
  "duration_ms": 293.318892,
  "end_unix_ns": 1784225794362057294,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-125e113a8b3742aa8adb57aa05b0df82",
  "start_unix_ns": 1784225794068738402,
  "timed_out": false,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
    "bash",
    "-c",
    "grep -R 'def concat' ."
  ],
  "command": "bash\u0000-c\u0000grep -R 'def concat' .",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "docker_operation": "exec",
  "duration_ms": 239.892106,
  "end_unix_ns": 1784225794759779133,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-ea8bacfeec444b8d88e0223a81286d5b",
  "start_unix_ns": 1784225794519887027,
  "timed_out": false,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\raw\api_boundary.jsonl` lines≈54 size=6301175
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0000-5fda6ada",
  "call_index": 0,
  "cost_usd": 0.005388,
  "derived_timing": {
    "upstream_body_ms": 0.0,
    "upstream_first_byte_ms": 7504.916561,
    "upstream_total_ms": 7504.916561
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbklnbm9yZSBtaXNzaW5nIHZhcmlhYmxlcyB3aGVuIGNvbmNhdGVuYXRpbmcgZGF0YXNldHM/XG5TZXZlcmFsIHVzZXJzIChAcmFqLWtlc2F2YW4sIEByaWNoYXJkb3Rpcywgbm93IG15c2VsZikgaGF2ZSB3b25kZXJlZCBhYm91dCBob3cgdG8gY29uY2F0ZW5hdGUgeHJheSBEYXRhc2V0cyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMuXG5cbldpdGggdGhlIGN1cnJlbnQgYHhyYXkuY29uY2F0YCwgeW91IG5lZWQgdG8gYXdrd2FyZGx5IGNyZWF0ZSBkdW1teSB2YXJpYWJsZXMgZmlsbGVkIHdpdGggYE5hTmAgaW4gZGF0YXNldHMgdGhhdCBkb24ndCBoYXZlIHRoZW0gKG9yIGRyb3AgbWlzbWF0Y2hlZCB2YXJpYWJsZXMgZW50aXJlbHkpLiBOZWl0aGVyIG9mIHRoZXNlIGFyZSBncmVhdCBvcHRpb25zIC0tIGBjb25jYXRgIHNob3VsZCBoYXZlIGFuIG9wdGlvbiAodGhlIGRlZmF1bHQ/KSB0byB0YWtlIGNhcmUgb2YgdGhpcyBmb3IgdGhlIHVzZXIuXG5cblRoaXMgd291bGQgYWxzbyBiZSBtb3JlIGNvbnNpc3RlbnQgd2l0aCBgcGQuY29uY2F0YCwgd2hpY2ggdGFrZXMgYSBtb3JlIHJlbGF4ZWQgYXBwcm9hY2ggdG8gbWF0Y2hpbmcgZGF0YWZyYW1lcyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMgKGl0IGRvZXMgYW4gb3V0ZXIgam9pbikuXG5cblxuPC9wcl9kZXNjcmlwdGlvbj5cblxuPGluc3RydWN0aW9ucz5cbiMgVGFzayBJbnN0cnVjdGlvbnNcblxuIyMgT3ZlcnZpZXdcblxuWW91J3JlIGEgc29mdHdhcmUgZW5naW5lZXIgaW50ZXJhY3RpbmcgY29udGludW91c2x5IHdpdGggYSBjb21wdXRlciBieSBzdWJtaXR0aW5nIGNvbW1hbmRzLlxuWW91J2xsIGJlIGhlbHBpbmcgaW1wbGVtZW50IG5lY2Vzc2FyeSBjaGFuZ2VzIHRvIG1lZXQgcmVxdWlyZW1lbnRzIGluIHRoZSBQUiBkZXNjcmlwdGlvbi5cbllvdXIgdGFzayBpcyBzcGVjaWZpY2FsbHkgdG8gbWFrZSBjaGFuZ2VzIHRvIG5vbi10ZXN0IGZpbGVzIGluIHRoZSBjdXJyZW50IGRpcmVjdG9yeSBpbiBvcmRlciB0byBmaXggdGhlIGlzc3VlIGRlc2NyaWJlZCBpbiB0aGUgUFIgZGVzY3JpcHRpb24gaW4gYSB3YXkgdGhhdCBpcyBnZW5lcmFsIGFuZCBjb25zaXN0ZW50IHdpdGggdGhlIGNvZGViYXNlLlxuPElNUE9SVEFOVD5UaGlzIGlzIGFuIGludGVyYWN0aXZlIHByb2Nlc3Mgd2hlcmUgeW91IHdpbGwgdGhpbmsgYW5kIGlzc3VlIEFUIExFQVNUIE9ORSBjb21tYW5kLCBzZWUgdGhlIHJlc3VsdCwgdGhlbiB0aGluayBhbmQgaXNzdWUgeW91ciBuZXh0IGNvbW1hbmQocykuPC9pbXBvcnRhbnQ+XG5cbkZvciBlYWNoIHJlc3BvbnNlOlxuXG4xLiBJbmNsdWRlIGEgVEhPVUdIVCBzZWN0aW9uIGV4cGxhaW5pbmcgeW91ciByZWFzb25pbmcgYW5kIHdoYXQgeW91J3JlIHRyeWluZyB0byBhY2NvbXBsaXNoXG4yLiBQcm92aWRlIG9uZSBvciBtb3JlIGJhc2ggdG9vbCBjYWxscyB0byBleGVjdXRlXG5cbiMjIEltcG9ydGFudCBCb3VuZGFyaWVzXG5cbi0gTU9ESUZZOiBSZWd1bGFyIHNvdXJjZSBjb2RlIGZpbGVzIGluIC90ZXN0YmVkICh0aGlzIGlzIHRoZSB3b3JraW5nIGRpcmVjdG9yeSBmb3IgYWxsIHlvdXIgc3Vic2VxdWVudCBjb21tYW5kcylcbi0gRE8gTk9UIE1PRElGWTogVGVzdHMsIGNvbmZpZ3VyYXRpb24gZmlsZXMgKHB5cHJvamVjdC50b21sLCBzZXR1cC5jZmcsIGV0Yy4pXG5cbiMjIFJlY29tbWVuZGVkIFdvcmtmbG93XG5cbjEuIEFuYWx5emUgdGhlIGNvZGViYXNlIGJ5IGZpbmRpbmcgYW5kIHJlYWRpbmcgcmVsZXZhbnQgZmlsZXNcbjIuIENyZWF0ZSBhIHNjcmlwdCB0byByZXByb2R1Y2UgdGhlIGlzc3VlXG4zLiBFZGl0IHRoZSBzb3VyY2UgY29kZSB0byByZXNvbHZlIHRoZSBpc3N1ZVxuNC4gVmVyaWZ5IHlvdXIgZml4IHdvcmtzIGJ5IHJ1bm5pbmcgeW91ciBzY3JpcHQgYWdhaW5cbjUuIFRlc3QgZWRnZSBjYXNlcyB0byBlbnN1cmUgeW91ciBmaXggaXMgcm9idXN0XG5cbiMjIENvbW1hbmQgRXhlY3V0aW9uIFJ1bGVzXG5cbllvdSBhcmUgb3BlcmF0aW5nIGluIGFuIGVudmlyb25tZW50IHdoZXJlXG5cbjEuIFlvdSBpc3N1ZSBhdCBsZWFzdCBvbmUgY29tbWFuZFxuMi4gVGhlIHN5c3RlbSBleGVjdXRlcyB0aGUgY29tbWFuZChzKSBpbiBhIHN1YnNoZWxsXG4zLiBZb3Ugc2VlIHRoZSByZXN1bHQocylcbjQuIFlvdSB3cml0ZSB5b3VyIG5leHQgY29tbWFuZChzKVxuXG5FYWNoIHJlc3BvbnNlIHNob3VsZCBpbmNsdWRlOlxuXG4xLiAqKlJlYXNvbmluZyB0ZXh0Kiogd2hlcmUgeW91IGV4cGxhaW4geW91ciBhbmFseXNpcyBhbmQgcGxhblxuMi4gQXQgbGVhc3Qgb25lIHRvb2wgY2FsbCB3aXRoIHlvdXIgY29tbWFuZFxuXG4qKkNSSVRJQ0FMIFJFUVVJUkVNRU5UUzoqKlxuXG4tIFlvdXIgcmVzcG9uc2UgU0hPVUxEIGluY2x1ZGUgcmVhc29uaW5nIHRleHQgZXhwbGFpbmluZyB3aGF0IHlvdSdyZSBkb2luZ1xuLSBZb3VyIHJlc3BvbnNlIE1VU1QgaW5jbHVkZSBBVCBMRUFTVCBPTkUgYmFzaCB0b29sIGNhbGwuIFlvdSBjYW4gbWFrZSBNV
```

### sample[1]
```json
{
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0001-a856003b",
  "call_index": 1,
  "cost_usd": 0.011004,
  "derived_timing": {
    "upstream_body_ms": 1.772216,
    "upstream_first_byte_ms": 8125.873318,
    "upstream_total_ms": 8127.645534
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbklnbm9yZSBtaXNzaW5nIHZhcmlhYmxlcyB3aGVuIGNvbmNhdGVuYXRpbmcgZGF0YXNldHM/XG5TZXZlcmFsIHVzZXJzIChAcmFqLWtlc2F2YW4sIEByaWNoYXJkb3Rpcywgbm93IG15c2VsZikgaGF2ZSB3b25kZXJlZCBhYm91dCBob3cgdG8gY29uY2F0ZW5hdGUgeHJheSBEYXRhc2V0cyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMuXG5cbldpdGggdGhlIGN1cnJlbnQgYHhyYXkuY29uY2F0YCwgeW91IG5lZWQgdG8gYXdrd2FyZGx5IGNyZWF0ZSBkdW1teSB2YXJpYWJsZXMgZmlsbGVkIHdpdGggYE5hTmAgaW4gZGF0YXNldHMgdGhhdCBkb24ndCBoYXZlIHRoZW0gKG9yIGRyb3AgbWlzbWF0Y2hlZCB2YXJpYWJsZXMgZW50aXJlbHkpLiBOZWl0aGVyIG9mIHRoZXNlIGFyZSBncmVhdCBvcHRpb25zIC0tIGBjb25jYXRgIHNob3VsZCBoYXZlIGFuIG9wdGlvbiAodGhlIGRlZmF1bHQ/KSB0byB0YWtlIGNhcmUgb2YgdGhpcyBmb3IgdGhlIHVzZXIuXG5cblRoaXMgd291bGQgYWxzbyBiZSBtb3JlIGNvbnNpc3RlbnQgd2l0aCBgcGQuY29uY2F0YCwgd2hpY2ggdGFrZXMgYSBtb3JlIHJlbGF4ZWQgYXBwcm9hY2ggdG8gbWF0Y2hpbmcgZGF0YWZyYW1lcyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMgKGl0IGRvZXMgYW4gb3V0ZXIgam9pbikuXG5cblxuPC9wcl9kZXNjcmlwdGlvbj5cblxuPGluc3RydWN0aW9ucz5cbiMgVGFzayBJbnN0cnVjdGlvbnNcblxuIyMgT3ZlcnZpZXdcblxuWW91J3JlIGEgc29mdHdhcmUgZW5naW5lZXIgaW50ZXJhY3RpbmcgY29udGludW91c2x5IHdpdGggYSBjb21wdXRlciBieSBzdWJtaXR0aW5nIGNvbW1hbmRzLlxuWW91J2xsIGJlIGhlbHBpbmcgaW1wbGVtZW50IG5lY2Vzc2FyeSBjaGFuZ2VzIHRvIG1lZXQgcmVxdWlyZW1lbnRzIGluIHRoZSBQUiBkZXNjcmlwdGlvbi5cbllvdXIgdGFzayBpcyBzcGVjaWZpY2FsbHkgdG8gbWFrZSBjaGFuZ2VzIHRvIG5vbi10ZXN0IGZpbGVzIGluIHRoZSBjdXJyZW50IGRpcmVjdG9yeSBpbiBvcmRlciB0byBmaXggdGhlIGlzc3VlIGRlc2NyaWJlZCBpbiB0aGUgUFIgZGVzY3JpcHRpb24gaW4gYSB3YXkgdGhhdCBpcyBnZW5lcmFsIGFuZCBjb25zaXN0ZW50IHdpdGggdGhlIGNvZGViYXNlLlxuPElNUE9SVEFOVD5UaGlzIGlzIGFuIGludGVyYWN0aXZlIHByb2Nlc3Mgd2hlcmUgeW91IHdpbGwgdGhpbmsgYW5kIGlzc3VlIEFUIExFQVNUIE9ORSBjb21tYW5kLCBzZWUgdGhlIHJlc3VsdCwgdGhlbiB0aGluayBhbmQgaXNzdWUgeW91ciBuZXh0IGNvbW1hbmQocykuPC9pbXBvcnRhbnQ+XG5cbkZvciBlYWNoIHJlc3BvbnNlOlxuXG4xLiBJbmNsdWRlIGEgVEhPVUdIVCBzZWN0aW9uIGV4cGxhaW5pbmcgeW91ciByZWFzb25pbmcgYW5kIHdoYXQgeW91J3JlIHRyeWluZyB0byBhY2NvbXBsaXNoXG4yLiBQcm92aWRlIG9uZSBvciBtb3JlIGJhc2ggdG9vbCBjYWxscyB0byBleGVjdXRlXG5cbiMjIEltcG9ydGFudCBCb3VuZGFyaWVzXG5cbi0gTU9ESUZZOiBSZWd1bGFyIHNvdXJjZSBjb2RlIGZpbGVzIGluIC90ZXN0YmVkICh0aGlzIGlzIHRoZSB3b3JraW5nIGRpcmVjdG9yeSBmb3IgYWxsIHlvdXIgc3Vic2VxdWVudCBjb21tYW5kcylcbi0gRE8gTk9UIE1PRElGWTogVGVzdHMsIGNvbmZpZ3VyYXRpb24gZmlsZXMgKHB5cHJvamVjdC50b21sLCBzZXR1cC5jZmcsIGV0Yy4pXG5cbiMjIFJlY29tbWVuZGVkIFdvcmtmbG93XG5cbjEuIEFuYWx5emUgdGhlIGNvZGViYXNlIGJ5IGZpbmRpbmcgYW5kIHJlYWRpbmcgcmVsZXZhbnQgZmlsZXNcbjIuIENyZWF0ZSBhIHNjcmlwdCB0byByZXByb2R1Y2UgdGhlIGlzc3VlXG4zLiBFZGl0IHRoZSBzb3VyY2UgY29kZSB0byByZXNvbHZlIHRoZSBpc3N1ZVxuNC4gVmVyaWZ5IHlvdXIgZml4IHdvcmtzIGJ5IHJ1bm5pbmcgeW91ciBzY3JpcHQgYWdhaW5cbjUuIFRlc3QgZWRnZSBjYXNlcyB0byBlbnN1cmUgeW91ciBmaXggaXMgcm9idXN0XG5cbiMjIENvbW1hbmQgRXhlY3V0aW9uIFJ1bGVzXG5cbllvdSBhcmUgb3BlcmF0aW5nIGluIGFuIGVudmlyb25tZW50IHdoZXJlXG5cbjEuIFlvdSBpc3N1ZSBhdCBsZWFzdCBvbmUgY29tbWFuZFxuMi4gVGhlIHN5c3RlbSBleGVjdXRlcyB0aGUgY29tbWFuZChzKSBpbiBhIHN1YnNoZWxsXG4zLiBZb3Ugc2VlIHRoZSByZXN1bHQocylcbjQuIFlvdSB3cml0ZSB5b3VyIG5leHQgY29tbWFuZChzKVxuXG5FYWNoIHJlc3BvbnNlIHNob3VsZCBpbmNsdWRlOlxuXG4xLiAqKlJlYXNvbmluZyB0ZXh0Kiogd2hlcmUgeW91IGV4cGxhaW4geW91ciBhbmFseXNpcyBhbmQgcGxhblxuMi4gQXQgbGVhc3Qgb25lIHRvb2wgY2FsbCB3aXRoIHlvdXIgY29tbWFuZFxuXG4qKkNSSVRJQ0FMIFJFUVVJUkVNRU5UUzoqKlxuXG4tIFlvdXIgcmVzcG9uc2UgU0hPVUxEIGluY2x1ZGUgcmVhc29uaW5nIHRleHQgZXhwbGFpbmluZyB3aGF0IHlvdSdyZSBkb2luZ1xuLSBZb3VyIHJlc3BvbnNlIE1VU1QgaW5jbHVkZSBBVCBMRUFTVCBPTkUgYmFzaCB0b29sIGNhbGwuIFlvdSBjYW4gbWFr
```

### sample[2]
```json
{
  "call_id": "OA01-M-03-pydata__xarray-3364-call-0002-f3b810e4",
  "call_index": 2,
  "cost_usd": 0.00707,
  "derived_timing": {
    "upstream_body_ms": 0.056735,
    "upstream_first_byte_ms": 10313.172241,
    "upstream_total_ms": 10313.228976
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbklnbm9yZSBtaXNzaW5nIHZhcmlhYmxlcyB3aGVuIGNvbmNhdGVuYXRpbmcgZGF0YXNldHM/XG5TZXZlcmFsIHVzZXJzIChAcmFqLWtlc2F2YW4sIEByaWNoYXJkb3Rpcywgbm93IG15c2VsZikgaGF2ZSB3b25kZXJlZCBhYm91dCBob3cgdG8gY29uY2F0ZW5hdGUgeHJheSBEYXRhc2V0cyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMuXG5cbldpdGggdGhlIGN1cnJlbnQgYHhyYXkuY29uY2F0YCwgeW91IG5lZWQgdG8gYXdrd2FyZGx5IGNyZWF0ZSBkdW1teSB2YXJpYWJsZXMgZmlsbGVkIHdpdGggYE5hTmAgaW4gZGF0YXNldHMgdGhhdCBkb24ndCBoYXZlIHRoZW0gKG9yIGRyb3AgbWlzbWF0Y2hlZCB2YXJpYWJsZXMgZW50aXJlbHkpLiBOZWl0aGVyIG9mIHRoZXNlIGFyZSBncmVhdCBvcHRpb25zIC0tIGBjb25jYXRgIHNob3VsZCBoYXZlIGFuIG9wdGlvbiAodGhlIGRlZmF1bHQ/KSB0byB0YWtlIGNhcmUgb2YgdGhpcyBmb3IgdGhlIHVzZXIuXG5cblRoaXMgd291bGQgYWxzbyBiZSBtb3JlIGNvbnNpc3RlbnQgd2l0aCBgcGQuY29uY2F0YCwgd2hpY2ggdGFrZXMgYSBtb3JlIHJlbGF4ZWQgYXBwcm9hY2ggdG8gbWF0Y2hpbmcgZGF0YWZyYW1lcyB3aXRoIGRpZmZlcmVudCB2YXJpYWJsZXMgKGl0IGRvZXMgYW4gb3V0ZXIgam9pbikuXG5cblxuPC9wcl9kZXNjcmlwdGlvbj5cblxuPGluc3RydWN0aW9ucz5cbiMgVGFzayBJbnN0cnVjdGlvbnNcblxuIyMgT3ZlcnZpZXdcblxuWW91J3JlIGEgc29mdHdhcmUgZW5naW5lZXIgaW50ZXJhY3RpbmcgY29udGludW91c2x5IHdpdGggYSBjb21wdXRlciBieSBzdWJtaXR0aW5nIGNvbW1hbmRzLlxuWW91J2xsIGJlIGhlbHBpbmcgaW1wbGVtZW50IG5lY2Vzc2FyeSBjaGFuZ2VzIHRvIG1lZXQgcmVxdWlyZW1lbnRzIGluIHRoZSBQUiBkZXNjcmlwdGlvbi5cbllvdXIgdGFzayBpcyBzcGVjaWZpY2FsbHkgdG8gbWFrZSBjaGFuZ2VzIHRvIG5vbi10ZXN0IGZpbGVzIGluIHRoZSBjdXJyZW50IGRpcmVjdG9yeSBpbiBvcmRlciB0byBmaXggdGhlIGlzc3VlIGRlc2NyaWJlZCBpbiB0aGUgUFIgZGVzY3JpcHRpb24gaW4gYSB3YXkgdGhhdCBpcyBnZW5lcmFsIGFuZCBjb25zaXN0ZW50IHdpdGggdGhlIGNvZGViYXNlLlxuPElNUE9SVEFOVD5UaGlzIGlzIGFuIGludGVyYWN0aXZlIHByb2Nlc3Mgd2hlcmUgeW91IHdpbGwgdGhpbmsgYW5kIGlzc3VlIEFUIExFQVNUIE9ORSBjb21tYW5kLCBzZWUgdGhlIHJlc3VsdCwgdGhlbiB0aGluayBhbmQgaXNzdWUgeW91ciBuZXh0IGNvbW1hbmQocykuPC9pbXBvcnRhbnQ+XG5cbkZvciBlYWNoIHJlc3BvbnNlOlxuXG4xLiBJbmNsdWRlIGEgVEhPVUdIVCBzZWN0aW9uIGV4cGxhaW5pbmcgeW91ciByZWFzb25pbmcgYW5kIHdoYXQgeW91J3JlIHRyeWluZyB0byBhY2NvbXBsaXNoXG4yLiBQcm92aWRlIG9uZSBvciBtb3JlIGJhc2ggdG9vbCBjYWxscyB0byBleGVjdXRlXG5cbiMjIEltcG9ydGFudCBCb3VuZGFyaWVzXG5cbi0gTU9ESUZZOiBSZWd1bGFyIHNvdXJjZSBjb2RlIGZpbGVzIGluIC90ZXN0YmVkICh0aGlzIGlzIHRoZSB3b3JraW5nIGRpcmVjdG9yeSBmb3IgYWxsIHlvdXIgc3Vic2VxdWVudCBjb21tYW5kcylcbi0gRE8gTk9UIE1PRElGWTogVGVzdHMsIGNvbmZpZ3VyYXRpb24gZmlsZXMgKHB5cHJvamVjdC50b21sLCBzZXR1cC5jZmcsIGV0Yy4pXG5cbiMjIFJlY29tbWVuZGVkIFdvcmtmbG93XG5cbjEuIEFuYWx5emUgdGhlIGNvZGViYXNlIGJ5IGZpbmRpbmcgYW5kIHJlYWRpbmcgcmVsZXZhbnQgZmlsZXNcbjIuIENyZWF0ZSBhIHNjcmlwdCB0byByZXByb2R1Y2UgdGhlIGlzc3VlXG4zLiBFZGl0IHRoZSBzb3VyY2UgY29kZSB0byByZXNvbHZlIHRoZSBpc3N1ZVxuNC4gVmVyaWZ5IHlvdXIgZml4IHdvcmtzIGJ5IHJ1bm5pbmcgeW91ciBzY3JpcHQgYWdhaW5cbjUuIFRlc3QgZWRnZSBjYXNlcyB0byBlbnN1cmUgeW91ciBmaXggaXMgcm9idXN0XG5cbiMjIENvbW1hbmQgRXhlY3V0aW9uIFJ1bGVzXG5cbllvdSBhcmUgb3BlcmF0aW5nIGluIGFuIGVudmlyb25tZW50IHdoZXJlXG5cbjEuIFlvdSBpc3N1ZSBhdCBsZWFzdCBvbmUgY29tbWFuZFxuMi4gVGhlIHN5c3RlbSBleGVjdXRlcyB0aGUgY29tbWFuZChzKSBpbiBhIHN1YnNoZWxsXG4zLiBZb3Ugc2VlIHRoZSByZXN1bHQocylcbjQuIFlvdSB3cml0ZSB5b3VyIG5leHQgY29tbWFuZChzKVxuXG5FYWNoIHJlc3BvbnNlIHNob3VsZCBpbmNsdWRlOlxuXG4xLiAqKlJlYXNvbmluZyB0ZXh0Kiogd2hlcmUgeW91IGV4cGxhaW4geW91ciBhbmFseXNpcyBhbmQgcGxhblxuMi4gQXQgbGVhc3Qgb25lIHRvb2wgY2FsbCB3aXRoIHlvdXIgY29tbWFuZFxuXG4qKkNSSVRJQ0FMIFJFUVVJUkVNRU5UUzoqKlxuXG4tIFlvdXIgcmVzcG9uc2UgU0hPVUxEIGluY2x1ZGUgcmVhc29uaW5nIHRleHQgZXhwbGFpbmluZyB3aGF0IHlvdSdyZSBkb2luZ1xuLSBZb3VyIHJlc3BvbnNlIE1VU1QgaW5jbHVkZSBBVCBMRUFTVCBPTkUgYmFzaCB0b29sIGNhbGwuIFlvdSBjYW4gbWF
```
- `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\raw\env_snapshots.jsonl` lines≈34 size=52862
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-125e113a8b3742aa8adb57aa05b0df82",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "exec_end_unix_ns": 1784225794362057294,
  "git_commit": "863e49066ca4d61c9adfe62aca3bf21b90e1af8c\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:5a32cf79c05cc8bb9cdca2553862b88a9ef682c2c1bd81e8027d41e4f8740e1e\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784225794768314149,
  "snapshot_start_unix_ns": 1784225794394416780,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-ea8bacfeec444b8d88e0223a81286d5b",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "exec_end_unix_ns": 1784225794759779133,
  "git_commit": "863e49066ca4d61c9adfe62aca3bf21b90e1af8c\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:5a32cf79c05cc8bb9cdca2553862b88a9ef682c2c1bd81e8027d41e4f8740e1e\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784225795146848240,
  "snapshot_start_unix_ns": 1784225794830469382,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-90d8783a44ab48bbb4ca146eab9539f4",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "exec_end_unix_ns": 1784225795145991374,
  "git_commit": "863e49066ca4d61c9adfe62aca3bf21b90e1af8c\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:5a32cf79c05cc8bb9cdca2553862b88a9ef682c2c1bd81e8027d41e4f8740e1e\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784225795515946131,
  "snapshot_start_unix_ns": 1784225795216520946,
  "trajectory_id": "OA01-M-03-pydata__xarray-3364"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\raw\exec_events.jsonl` lines≈72 size=68114
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-b50a6a19",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pydata_1776_xarray-3364:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-9036340160ef482c962971b9ed85b8f9",
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "unix_ns": 1784225782794356097
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-b50a6a19",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pydata_1776_xarray-3364:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-9036340160ef482c962971b9ed85b8f9",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-03-pydata__xarray-3364/raw/tool_io/exec-9036340160ef482c962971b9ed85b8f9.stdout_stderr.bin",
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "unix_ns": 1784225783075835559
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
    "bash",
    "-c",
    "ls -l"
  ],
  "command": "bash\u0000-c\u0000ls -l",
  "container_id": "3448646a44334616ea9fed5e2268f2f8b891705ec0b4b42426674ef7f3858dd0",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-125e113a8b3742aa8adb57aa05b0df82",
  "trajectory_id": "OA01-M-03-pydata__xarray-3364",
  "unix_ns": 1784225794068738402
}
```
- `apu_characterization\out\oa01\runs\OA01-M-04-matplotlib__matplotlib-25332\derived\exec_spans.jsonl` lines≈17 size=13755
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-8d4e6de4",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-25332:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 618.438561,
  "end_unix_ns": 1784226413647652060,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-8c5837f1120d47e595efe314d773a900",
  "start_unix_ns": 1784226413029213499,
  "timed_out": false,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
    "bash",
    "-c",
    "grep -rn 'def align_labels' /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -rn 'def align_labels' /testbed",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "docker_operation": "exec",
  "duration_ms": 8603.020579,
  "end_unix_ns": 1784226432227387947,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-b96638b2d8b44e2494fabd74e296e4ba",
  "start_unix_ns": 1784226423624367368,
  "timed_out": false,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
    "bash",
    "-c",
    "grep -rn weakref /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -rn weakref /testbed",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "docker_operation": "exec",
  "duration_ms": 934.049182,
  "end_unix_ns": 1784226433400165763,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-670a641a33614756bdd85deb1f04d539",
  "start_unix_ns": 1784226432466116581,
  "timed_out": false,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-04-matplotlib__matplotlib-25332\raw\api_boundary.jsonl` lines≈14 size=925628
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-04-matplotlib__matplotlib-25332-call-0000-00e76233",
  "call_index": 0,
  "cost_usd": 0.004446,
  "derived_timing": {
    "upstream_body_ms": 0.088336,
    "upstream_first_byte_ms": 4210.684162,
    "upstream_total_ms": 4210.772498
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSB3aXRoIGFsaWduZWQgbGFiZWxzXG4jIyMgQnVnIHN1bW1hcnlcclxuXHJcbiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSBhZnRlciBjYWxsaW5nIGBhbGlnbl9sYWJlbHMoKWBcclxuXHJcbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cclxuXHJcbmBgYHB5dGhvblxyXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcGx0XHJcbmltcG9ydCBwaWNrbGVcclxuXHJcbmZpZyA9IHBsdC5maWd1cmUoKVxyXG5heDEgPSBmaWcuYWRkX3N1YnBsb3QoMjExKVxyXG5heDIgPSBmaWcuYWRkX3N1YnBsb3QoMjEyKVxyXG50aW1lPVswLDEsMiwzLDRdXHJcbnNwZWVkPVs0MDAwMCw0MzAwLDQ1MDAsNDcwMCw0ODAwXVxyXG5hY2M9WzEwLDExLDEyLDEzLDE0XVxyXG5heDEucGxvdCh0aW1lLHNwZWVkKVxyXG5heDEuc2V0X3lsYWJlbCgnc3BlZWQnKVxyXG5heDIucGxvdCh0aW1lLGFjYylcclxuYXgyLnNldF95bGFiZWwoJ2FjYycpXHJcblxyXG5maWcuYWxpZ25fbGFiZWxzKCkgIyNwaWNrbGluZyB3b3JrcyBhZnRlciByZW1vdmluZyB0aGlzIGxpbmUgXHJcblxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5wbHQuc2hvdygpXHJcbmBgYFxyXG5cclxuXHJcbiMjIyBBY3R1YWwgb3V0Y29tZVxyXG5gYGBcclxuYWxpZ24ucHlcIiwgbGluZSAxNlxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5UeXBlRXJyb3I6IGNhbm5vdCBwaWNrbGUgJ3dlYWtyZWYuUmVmZXJlbmNlVHlwZScgb2JqZWN0XHJcbmBgYFxyXG4jIyMgRXhwZWN0ZWQgb3V0Y29tZVxyXG5cclxuUGlja2xpbmcgc3VjY2Vzc2Z1bFxyXG5cclxuIyMjIEFkZGl0aW9uYWwgaW5mb3JtYXRpb25cclxuXHJcbl9ObyByZXNwb25zZV9cclxuXHJcbiMjIyBPcGVyYXRpbmcgc3lzdGVtXHJcblxyXG5XaW5kb3dzXHJcblxyXG4jIyMgTWF0cGxvdGxpYiBWZXJzaW9uXHJcblxyXG4zLjcuMFxyXG5cclxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxyXG5cclxuX05vIHJlc3BvbnNlX1xyXG5cclxuIyMjIFB5dGhvbiB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSnVweXRlciB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSW5zdGFsbGF0aW9uXHJcblxyXG5Ob25lXG5cbjwvcHJfZGVzY3JpcHRpb24+XG5cbjxpbnN0cnVjdGlvbnM+XG4jIFRhc2sgSW5zdHJ1Y3Rpb25zXG5cbiMjIE92ZXJ2aWV3XG5cbllvdSdyZSBhIHNvZnR3YXJlIGVuZ2luZWVyIGludGVyYWN0aW5nIGNvbnRpbnVvdXNseSB3aXRoIGEgY29tcHV0ZXIgYnkgc3VibWl0dGluZyBjb21tYW5kcy5cbllvdSdsbCBiZSBoZWxwaW5nIGltcGxlbWVudCBuZWNlc3NhcnkgY2hhbmdlcyB0byBtZWV0IHJlcXVpcmVtZW50cyBpbiB0aGUgUFIgZGVzY3JpcHRpb24uXG5Zb3VyIHRhc2sgaXMgc3BlY2lmaWNhbGx5IHRvIG1ha2UgY2hhbmdlcyB0byBub24tdGVzdCBmaWxlcyBpbiB0aGUgY3VycmVudCBkaXJlY3RvcnkgaW4gb3JkZXIgdG8gZml4IHRoZSBpc3N1ZSBkZXNjcmliZWQgaW4gdGhlIFBSIGRlc2NyaXB0aW9uIGluIGEgd2F5IHRoYXQgaXMgZ2VuZXJhbCBhbmQgY29uc2lzdGVudCB3aXRoIHRoZSBjb2RlYmFzZS5cbjxJTVBPUlRBTlQ+VGhpcyBpcyBhbiBpbnRlcmFjdGl2ZSBwcm9jZXNzIHdoZXJlIHlvdSB3aWxsIHRoaW5rIGFuZCBpc3N1ZSBBVCBMRUFTVCBPTkUgY29tbWFuZCwgc2VlIHRoZSByZXN1bHQsIHRoZW4gdGhpbmsgYW5kIGlzc3VlIHlvdXIgbmV4dCBjb21tYW5kKHMpLjwvaW1wb3J0YW50PlxuXG5Gb3IgZWFjaCByZXNwb25zZTpcblxuMS4gSW5jbHVkZSBhIFRIT1VHSFQgc2VjdGlvbiBleHBsYWluaW5nIHlvdXIgcmVhc29uaW5nIGFuZCB3aGF0IHlvdSdyZSB0cnlpbmcgdG8gYWNjb21wbGlzaFxuMi4gUHJvdmlkZSBvbmUgb3IgbW9yZSBiYXNoIHRvb2wgY2FsbHMgdG8gZXhlY3V0ZVxuXG4jIyBJbXBvcnRhbnQgQm91bmRhcmllc1xuXG4tIE1PRElGWTogUmVndWxhciBzb3VyY2UgY29kZSBmaWxlcyBpbiAvdGVzdGJlZCAodGhpcyBpcyB0aGUgd29ya2luZyBkaXJlY3RvcnkgZm9yIGFsbCB5b3VyIHN1YnNlcXVlbnQgY29tbWFuZHMpXG4tIERPIE5PVCBNT0RJRlk6IFRlc3RzLCBjb25maWd1cmF0aW9uIGZpbGVzIChweXByb2plY3QudG9tbCwgc2V0dXAuY2ZnLCBldGMuKVxuXG4jIyBSZWNvbW1lbmRlZCBXb3JrZmxvd1xuXG4xLiBBbmFseXplIHRoZSBjb2RlYmFzZSBieSBmaW5kaW5nIGFuZCByZWFkaW5nIHJlbGV2YW50IGZpbGVzXG4yLiBDcmVhdGUgYSBzY3JpcHQgdG8gcmVwcm9kdWNlIHRoZSBpc3N1ZVxuMy4gRWRpdCB0aGUgc291cmNlIGNvZGUgdG8gcmVzb2x2ZSB0aGUgaXNzdWVcbjQuIFZlcmlmeSB5b3VyIGZpeCB3b3JrcyBieSBydW5uaW5nIHlvdXIgc2NyaXB0IGFnYWluXG41LiBUZXN0IGVkZ2UgY2FzZXMgdG8gZW5zdXJlIHlvdXIgZml4IGlzIHJvYnVzdFxuXG4jIyBDb21tYW5kIEV4ZWN1dGlvbiBSdWxlc1xuXG5Zb3UgYXJlIG9wZXJhdGluZyBpbiB
```

### sample[1]
```json
{
  "call_id": "OA01-M-04-matplotlib__matplotlib-25332-call-0001-90610bbd",
  "call_index": 1,
  "cost_usd": 0.010746,
  "derived_timing": {
    "upstream_body_ms": 0.076788,
    "upstream_first_byte_ms": 9073.471544,
    "upstream_total_ms": 9073.548332
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSB3aXRoIGFsaWduZWQgbGFiZWxzXG4jIyMgQnVnIHN1bW1hcnlcclxuXHJcbiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSBhZnRlciBjYWxsaW5nIGBhbGlnbl9sYWJlbHMoKWBcclxuXHJcbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cclxuXHJcbmBgYHB5dGhvblxyXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcGx0XHJcbmltcG9ydCBwaWNrbGVcclxuXHJcbmZpZyA9IHBsdC5maWd1cmUoKVxyXG5heDEgPSBmaWcuYWRkX3N1YnBsb3QoMjExKVxyXG5heDIgPSBmaWcuYWRkX3N1YnBsb3QoMjEyKVxyXG50aW1lPVswLDEsMiwzLDRdXHJcbnNwZWVkPVs0MDAwMCw0MzAwLDQ1MDAsNDcwMCw0ODAwXVxyXG5hY2M9WzEwLDExLDEyLDEzLDE0XVxyXG5heDEucGxvdCh0aW1lLHNwZWVkKVxyXG5heDEuc2V0X3lsYWJlbCgnc3BlZWQnKVxyXG5heDIucGxvdCh0aW1lLGFjYylcclxuYXgyLnNldF95bGFiZWwoJ2FjYycpXHJcblxyXG5maWcuYWxpZ25fbGFiZWxzKCkgIyNwaWNrbGluZyB3b3JrcyBhZnRlciByZW1vdmluZyB0aGlzIGxpbmUgXHJcblxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5wbHQuc2hvdygpXHJcbmBgYFxyXG5cclxuXHJcbiMjIyBBY3R1YWwgb3V0Y29tZVxyXG5gYGBcclxuYWxpZ24ucHlcIiwgbGluZSAxNlxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5UeXBlRXJyb3I6IGNhbm5vdCBwaWNrbGUgJ3dlYWtyZWYuUmVmZXJlbmNlVHlwZScgb2JqZWN0XHJcbmBgYFxyXG4jIyMgRXhwZWN0ZWQgb3V0Y29tZVxyXG5cclxuUGlja2xpbmcgc3VjY2Vzc2Z1bFxyXG5cclxuIyMjIEFkZGl0aW9uYWwgaW5mb3JtYXRpb25cclxuXHJcbl9ObyByZXNwb25zZV9cclxuXHJcbiMjIyBPcGVyYXRpbmcgc3lzdGVtXHJcblxyXG5XaW5kb3dzXHJcblxyXG4jIyMgTWF0cGxvdGxpYiBWZXJzaW9uXHJcblxyXG4zLjcuMFxyXG5cclxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxyXG5cclxuX05vIHJlc3BvbnNlX1xyXG5cclxuIyMjIFB5dGhvbiB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSnVweXRlciB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSW5zdGFsbGF0aW9uXHJcblxyXG5Ob25lXG5cbjwvcHJfZGVzY3JpcHRpb24+XG5cbjxpbnN0cnVjdGlvbnM+XG4jIFRhc2sgSW5zdHJ1Y3Rpb25zXG5cbiMjIE92ZXJ2aWV3XG5cbllvdSdyZSBhIHNvZnR3YXJlIGVuZ2luZWVyIGludGVyYWN0aW5nIGNvbnRpbnVvdXNseSB3aXRoIGEgY29tcHV0ZXIgYnkgc3VibWl0dGluZyBjb21tYW5kcy5cbllvdSdsbCBiZSBoZWxwaW5nIGltcGxlbWVudCBuZWNlc3NhcnkgY2hhbmdlcyB0byBtZWV0IHJlcXVpcmVtZW50cyBpbiB0aGUgUFIgZGVzY3JpcHRpb24uXG5Zb3VyIHRhc2sgaXMgc3BlY2lmaWNhbGx5IHRvIG1ha2UgY2hhbmdlcyB0byBub24tdGVzdCBmaWxlcyBpbiB0aGUgY3VycmVudCBkaXJlY3RvcnkgaW4gb3JkZXIgdG8gZml4IHRoZSBpc3N1ZSBkZXNjcmliZWQgaW4gdGhlIFBSIGRlc2NyaXB0aW9uIGluIGEgd2F5IHRoYXQgaXMgZ2VuZXJhbCBhbmQgY29uc2lzdGVudCB3aXRoIHRoZSBjb2RlYmFzZS5cbjxJTVBPUlRBTlQ+VGhpcyBpcyBhbiBpbnRlcmFjdGl2ZSBwcm9jZXNzIHdoZXJlIHlvdSB3aWxsIHRoaW5rIGFuZCBpc3N1ZSBBVCBMRUFTVCBPTkUgY29tbWFuZCwgc2VlIHRoZSByZXN1bHQsIHRoZW4gdGhpbmsgYW5kIGlzc3VlIHlvdXIgbmV4dCBjb21tYW5kKHMpLjwvaW1wb3J0YW50PlxuXG5Gb3IgZWFjaCByZXNwb25zZTpcblxuMS4gSW5jbHVkZSBhIFRIT1VHSFQgc2VjdGlvbiBleHBsYWluaW5nIHlvdXIgcmVhc29uaW5nIGFuZCB3aGF0IHlvdSdyZSB0cnlpbmcgdG8gYWNjb21wbGlzaFxuMi4gUHJvdmlkZSBvbmUgb3IgbW9yZSBiYXNoIHRvb2wgY2FsbHMgdG8gZXhlY3V0ZVxuXG4jIyBJbXBvcnRhbnQgQm91bmRhcmllc1xuXG4tIE1PRElGWTogUmVndWxhciBzb3VyY2UgY29kZSBmaWxlcyBpbiAvdGVzdGJlZCAodGhpcyBpcyB0aGUgd29ya2luZyBkaXJlY3RvcnkgZm9yIGFsbCB5b3VyIHN1YnNlcXVlbnQgY29tbWFuZHMpXG4tIERPIE5PVCBNT0RJRlk6IFRlc3RzLCBjb25maWd1cmF0aW9uIGZpbGVzIChweXByb2plY3QudG9tbCwgc2V0dXAuY2ZnLCBldGMuKVxuXG4jIyBSZWNvbW1lbmRlZCBXb3JrZmxvd1xuXG4xLiBBbmFseXplIHRoZSBjb2RlYmFzZSBieSBmaW5kaW5nIGFuZCByZWFkaW5nIHJlbGV2YW50IGZpbGVzXG4yLiBDcmVhdGUgYSBzY3JpcHQgdG8gcmVwcm9kdWNlIHRoZSBpc3N1ZVxuMy4gRWRpdCB0aGUgc291cmNlIGNvZGUgdG8gcmVzb2x2ZSB0aGUgaXNzdWVcbjQuIFZlcmlmeSB5b3VyIGZpeCB3b3JrcyBieSBydW5uaW5nIHlvdXIgc2NyaXB0IGFnYWluXG41LiBUZXN0IGVkZ2UgY2FzZXMgdG8gZW5zdXJlIHlvdXIgZml4IGlzIHJvYnVzdFxuXG4jIyBDb21tYW5kIEV4ZWN1dGlvbiBSdWxlc1xuXG5Zb3UgYXJlIG9wZXJhdGluZyBpbiB
```

### sample[2]
```json
{
  "call_id": "OA01-M-04-matplotlib__matplotlib-25332-call-0002-e59dc2cb",
  "call_index": 2,
  "cost_usd": 0.007034,
  "derived_timing": {
    "upstream_body_ms": 0.0,
    "upstream_first_byte_ms": 5561.758184,
    "upstream_total_ms": 5561.758184
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSB3aXRoIGFsaWduZWQgbGFiZWxzXG4jIyMgQnVnIHN1bW1hcnlcclxuXHJcbiBVbmFibGUgdG8gcGlja2xlIGZpZ3VyZSBhZnRlciBjYWxsaW5nIGBhbGlnbl9sYWJlbHMoKWBcclxuXHJcbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cclxuXHJcbmBgYHB5dGhvblxyXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcGx0XHJcbmltcG9ydCBwaWNrbGVcclxuXHJcbmZpZyA9IHBsdC5maWd1cmUoKVxyXG5heDEgPSBmaWcuYWRkX3N1YnBsb3QoMjExKVxyXG5heDIgPSBmaWcuYWRkX3N1YnBsb3QoMjEyKVxyXG50aW1lPVswLDEsMiwzLDRdXHJcbnNwZWVkPVs0MDAwMCw0MzAwLDQ1MDAsNDcwMCw0ODAwXVxyXG5hY2M9WzEwLDExLDEyLDEzLDE0XVxyXG5heDEucGxvdCh0aW1lLHNwZWVkKVxyXG5heDEuc2V0X3lsYWJlbCgnc3BlZWQnKVxyXG5heDIucGxvdCh0aW1lLGFjYylcclxuYXgyLnNldF95bGFiZWwoJ2FjYycpXHJcblxyXG5maWcuYWxpZ25fbGFiZWxzKCkgIyNwaWNrbGluZyB3b3JrcyBhZnRlciByZW1vdmluZyB0aGlzIGxpbmUgXHJcblxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5wbHQuc2hvdygpXHJcbmBgYFxyXG5cclxuXHJcbiMjIyBBY3R1YWwgb3V0Y29tZVxyXG5gYGBcclxuYWxpZ24ucHlcIiwgbGluZSAxNlxyXG5waWNrbGUuZHVtcHMoZmlnKVxyXG5UeXBlRXJyb3I6IGNhbm5vdCBwaWNrbGUgJ3dlYWtyZWYuUmVmZXJlbmNlVHlwZScgb2JqZWN0XHJcbmBgYFxyXG4jIyMgRXhwZWN0ZWQgb3V0Y29tZVxyXG5cclxuUGlja2xpbmcgc3VjY2Vzc2Z1bFxyXG5cclxuIyMjIEFkZGl0aW9uYWwgaW5mb3JtYXRpb25cclxuXHJcbl9ObyByZXNwb25zZV9cclxuXHJcbiMjIyBPcGVyYXRpbmcgc3lzdGVtXHJcblxyXG5XaW5kb3dzXHJcblxyXG4jIyMgTWF0cGxvdGxpYiBWZXJzaW9uXHJcblxyXG4zLjcuMFxyXG5cclxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxyXG5cclxuX05vIHJlc3BvbnNlX1xyXG5cclxuIyMjIFB5dGhvbiB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSnVweXRlciB2ZXJzaW9uXHJcblxyXG5fTm8gcmVzcG9uc2VfXHJcblxyXG4jIyMgSW5zdGFsbGF0aW9uXHJcblxyXG5Ob25lXG5cbjwvcHJfZGVzY3JpcHRpb24+XG5cbjxpbnN0cnVjdGlvbnM+XG4jIFRhc2sgSW5zdHJ1Y3Rpb25zXG5cbiMjIE92ZXJ2aWV3XG5cbllvdSdyZSBhIHNvZnR3YXJlIGVuZ2luZWVyIGludGVyYWN0aW5nIGNvbnRpbnVvdXNseSB3aXRoIGEgY29tcHV0ZXIgYnkgc3VibWl0dGluZyBjb21tYW5kcy5cbllvdSdsbCBiZSBoZWxwaW5nIGltcGxlbWVudCBuZWNlc3NhcnkgY2hhbmdlcyB0byBtZWV0IHJlcXVpcmVtZW50cyBpbiB0aGUgUFIgZGVzY3JpcHRpb24uXG5Zb3VyIHRhc2sgaXMgc3BlY2lmaWNhbGx5IHRvIG1ha2UgY2hhbmdlcyB0byBub24tdGVzdCBmaWxlcyBpbiB0aGUgY3VycmVudCBkaXJlY3RvcnkgaW4gb3JkZXIgdG8gZml4IHRoZSBpc3N1ZSBkZXNjcmliZWQgaW4gdGhlIFBSIGRlc2NyaXB0aW9uIGluIGEgd2F5IHRoYXQgaXMgZ2VuZXJhbCBhbmQgY29uc2lzdGVudCB3aXRoIHRoZSBjb2RlYmFzZS5cbjxJTVBPUlRBTlQ+VGhpcyBpcyBhbiBpbnRlcmFjdGl2ZSBwcm9jZXNzIHdoZXJlIHlvdSB3aWxsIHRoaW5rIGFuZCBpc3N1ZSBBVCBMRUFTVCBPTkUgY29tbWFuZCwgc2VlIHRoZSByZXN1bHQsIHRoZW4gdGhpbmsgYW5kIGlzc3VlIHlvdXIgbmV4dCBjb21tYW5kKHMpLjwvaW1wb3J0YW50PlxuXG5Gb3IgZWFjaCByZXNwb25zZTpcblxuMS4gSW5jbHVkZSBhIFRIT1VHSFQgc2VjdGlvbiBleHBsYWluaW5nIHlvdXIgcmVhc29uaW5nIGFuZCB3aGF0IHlvdSdyZSB0cnlpbmcgdG8gYWNjb21wbGlzaFxuMi4gUHJvdmlkZSBvbmUgb3IgbW9yZSBiYXNoIHRvb2wgY2FsbHMgdG8gZXhlY3V0ZVxuXG4jIyBJbXBvcnRhbnQgQm91bmRhcmllc1xuXG4tIE1PRElGWTogUmVndWxhciBzb3VyY2UgY29kZSBmaWxlcyBpbiAvdGVzdGJlZCAodGhpcyBpcyB0aGUgd29ya2luZyBkaXJlY3RvcnkgZm9yIGFsbCB5b3VyIHN1YnNlcXVlbnQgY29tbWFuZHMpXG4tIERPIE5PVCBNT0RJRlk6IFRlc3RzLCBjb25maWd1cmF0aW9uIGZpbGVzIChweXByb2plY3QudG9tbCwgc2V0dXAuY2ZnLCBldGMuKVxuXG4jIyBSZWNvbW1lbmRlZCBXb3JrZmxvd1xuXG4xLiBBbmFseXplIHRoZSBjb2RlYmFzZSBieSBmaW5kaW5nIGFuZCByZWFkaW5nIHJlbGV2YW50IGZpbGVzXG4yLiBDcmVhdGUgYSBzY3JpcHQgdG8gcmVwcm9kdWNlIHRoZSBpc3N1ZVxuMy4gRWRpdCB0aGUgc291cmNlIGNvZGUgdG8gcmVzb2x2ZSB0aGUgaXNzdWVcbjQuIFZlcmlmeSB5b3VyIGZpeCB3b3JrcyBieSBydW5uaW5nIHlvdXIgc2NyaXB0IGFnYWluXG41LiBUZXN0IGVkZ2UgY2FzZXMgdG8gZW5zdXJlIHlvdXIgZml4IGlzIHJvYnVzdFxuXG4jIyBDb21tYW5kIEV4ZWN1dGlvbiBSdWxlc1xuXG5Zb3UgYXJlIG9wZXJhdGluZyBpbiBhbiBl
```
- `apu_characterization\out\oa01\runs\OA01-M-04-matplotlib__matplotlib-25332\raw\env_snapshots.jsonl` lines≈15 size=15345
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-b96638b2d8b44e2494fabd74e296e4ba",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "exec_end_unix_ns": 1784226432227387947,
  "git_commit": "66ba515e671638971bd11a34cff12c107a437e0b\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:1a2f954f46cbf464e1b7b1439c75050bd81fd1205252a0bb3fa066eaf49197a6\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226433490863408,
  "snapshot_start_unix_ns": 1784226432232406045,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-670a641a33614756bdd85deb1f04d539",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "exec_end_unix_ns": 1784226433400165763,
  "git_commit": "66ba515e671638971bd11a34cff12c107a437e0b\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:1a2f954f46cbf464e1b7b1439c75050bd81fd1205252a0bb3fa066eaf49197a6\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226434023056873,
  "snapshot_start_unix_ns": 1784226433555487922,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-3989a0170af849cbb60e11eb1eca1637",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "exec_end_unix_ns": 1784226433832682336,
  "git_commit": "66ba515e671638971bd11a34cff12c107a437e0b\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:1a2f954f46cbf464e1b7b1439c75050bd81fd1205252a0bb3fa066eaf49197a6\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226434542318593,
  "snapshot_start_unix_ns": 1784226434115055144,
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-04-matplotlib__matplotlib-25332\raw\exec_events.jsonl` lines≈34 size=26408
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-8d4e6de4",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-25332:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-8c5837f1120d47e595efe314d773a900",
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332",
  "unix_ns": 1784226413029213499
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-8d4e6de4",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-25332:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-8c5837f1120d47e595efe314d773a900",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-04-matplotlib__matplotlib-25332/raw/tool_io/exec-8c5837f1120d47e595efe314d773a900.stdout_stderr.bin",
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332",
  "unix_ns": 1784226413647652060
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
    "bash",
    "-c",
    "grep -rn 'def align_labels' /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -rn 'def align_labels' /testbed",
  "container_id": "efcbe5d535e3569dee3244ad10d811dc93c1249de605aae9cb646c16a192b107",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-b96638b2d8b44e2494fabd74e296e4ba",
  "trajectory_id": "OA01-M-04-matplotlib__matplotlib-25332",
  "unix_ns": 1784226423624367368
}
```
- `apu_characterization\out\oa01\runs\OA01-M-05-django__django-13925\derived\exec_spans.jsonl` lines≈17 size=13498
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ee32d914",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.django_1776_django-13925:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 292.481999,
  "end_unix_ns": 1784226601322053230,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-de10e8d71456430eb2f35cdf81f2f522",
  "start_unix_ns": 1784226601029571231,
  "timed_out": false,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
    "bash",
    "-c",
    "ls -lR /testbed"
  ],
  "command": "bash\u0000-c\u0000ls -lR /testbed",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "docker_operation": "exec",
  "duration_ms": 1170.776355,
  "end_unix_ns": 1784226616588289500,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-32a44a4330cc4f308141798b27f0c872",
  "start_unix_ns": 1784226615417513145,
  "timed_out": false,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
    "bash",
    "-c",
    "grep -r \"models.Model\" /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -r \"models.Model\" /testbed",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "docker_operation": "exec",
  "duration_ms": 3853.614456,
  "end_unix_ns": 1784226620950459841,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-65b15f2fdb40420bb9c09a5c5d02813e",
  "start_unix_ns": 1784226617096845385,
  "timed_out": false,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-05-django__django-13925\raw\api_boundary.jsonl` lines≈20 size=4229567
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-05-django__django-13925-call-0000-ca0d3ce5",
  "call_index": 0,
  "cost_usd": 0.006936,
  "derived_timing": {
    "upstream_body_ms": 0.161375,
    "upstream_first_byte_ms": 9821.31869,
    "upstream_total_ms": 9821.480065
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbm1vZGVscy5XMDQyIGlzIHJhaXNlZCBvbiBpbmhlcml0ZWQgbWFudWFsbHkgc3BlY2lmaWVkIHByaW1hcnkga2V5LlxuRGVzY3JpcHRpb25cblx0XG5JIGhhdmUgbW9kZWxzIHdoaWNoIGluaGVyaXQgZnJvbSBvdGhlciBtb2RlbHMsIGFuZCB0aGV5IHNob3VsZCBpbmhlcml0IHRoZSBwcmltYXJ5IGtleS4gVGhpcyB3b3JrcyBmaW5lIHdpdGggRGphbmdvIDMuMS4gSG93ZXZlciwgaWYgSSBpbnN0YWxsIERqYW5nbyAzLjIgYWxwaGEsIHdoZW4gSSBydW4gbWFrZV9taWdyYXRpb25zIEkgZ2V0IHRoZSBmb2xsb3dpbmcgZXJyb3IgbWVzc2FnZXM6XG5TeXN0ZW0gY2hlY2sgaWRlbnRpZmllZCBzb21lIGlzc3VlczpcbldBUk5JTkdTOlxuYWNjb3VudHMuUmVzZXJ2ZWRVc2VybmFtZTogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYWNjb3VudHMuVXNlcjogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYmxvY2tzLkJsb2NrOiAobW9kZWxzLlcwNDIpIEF1dG8tY3JlYXRlZCBwcmltYXJ5IGtleSB1c2VkIHdoZW4gbm90IGRlZmluaW5nIGEgcHJpbWFyeSBrZXkgdHlwZSwgYnkgZGVmYXVsdCAnZGphbmdvLmRiLm1vZGVscy5BdXRvRmllbGQnLlxuXHRcdEhJTlQ6IENvbmZpZ3VyZSB0aGUgREVGQVVMVF9BVVRPX0ZJRUxEIHNldHRpbmcgb3IgdGhlIEFwcENvbmZpZy5kZWZhdWx0X2F1dG9fZmllbGQgYXR0cmlidXRlIHRvIHBvaW50IHRvIGEgc3ViY2xhc3Mgb2YgQXV0b0ZpZWxkLCBlLmcuICdkamFuZ28uZGIubW9kZWxzLkJpZ0F1dG9GaWVsZCcuXG5jb250YWN0X2J5X2Zvcm0uRmVlZGJhY2s6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZBVUxUX0FVVE9fRklFTEQgc2V0dGluZyBvciB0aGUgU3BlZWR5Q29yZUNvbnRhY3RCeUZvcm1Db25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuY29yZV9tZXNzYWdlcy5SZWFkTWFyazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlTWVzc2FnZXNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5CbG9jazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBBcHBDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5Gb2xsb3c6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZB
```

### sample[1]
```json
{
  "call_id": "OA01-M-05-django__django-13925-call-0001-645d42c1",
  "call_index": 1,
  "cost_usd": 0.024554,
  "derived_timing": {
    "upstream_body_ms": 0.035739,
    "upstream_first_byte_ms": 9221.397488,
    "upstream_total_ms": 9221.433227
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbm1vZGVscy5XMDQyIGlzIHJhaXNlZCBvbiBpbmhlcml0ZWQgbWFudWFsbHkgc3BlY2lmaWVkIHByaW1hcnkga2V5LlxuRGVzY3JpcHRpb25cblx0XG5JIGhhdmUgbW9kZWxzIHdoaWNoIGluaGVyaXQgZnJvbSBvdGhlciBtb2RlbHMsIGFuZCB0aGV5IHNob3VsZCBpbmhlcml0IHRoZSBwcmltYXJ5IGtleS4gVGhpcyB3b3JrcyBmaW5lIHdpdGggRGphbmdvIDMuMS4gSG93ZXZlciwgaWYgSSBpbnN0YWxsIERqYW5nbyAzLjIgYWxwaGEsIHdoZW4gSSBydW4gbWFrZV9taWdyYXRpb25zIEkgZ2V0IHRoZSBmb2xsb3dpbmcgZXJyb3IgbWVzc2FnZXM6XG5TeXN0ZW0gY2hlY2sgaWRlbnRpZmllZCBzb21lIGlzc3VlczpcbldBUk5JTkdTOlxuYWNjb3VudHMuUmVzZXJ2ZWRVc2VybmFtZTogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYWNjb3VudHMuVXNlcjogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYmxvY2tzLkJsb2NrOiAobW9kZWxzLlcwNDIpIEF1dG8tY3JlYXRlZCBwcmltYXJ5IGtleSB1c2VkIHdoZW4gbm90IGRlZmluaW5nIGEgcHJpbWFyeSBrZXkgdHlwZSwgYnkgZGVmYXVsdCAnZGphbmdvLmRiLm1vZGVscy5BdXRvRmllbGQnLlxuXHRcdEhJTlQ6IENvbmZpZ3VyZSB0aGUgREVGQVVMVF9BVVRPX0ZJRUxEIHNldHRpbmcgb3IgdGhlIEFwcENvbmZpZy5kZWZhdWx0X2F1dG9fZmllbGQgYXR0cmlidXRlIHRvIHBvaW50IHRvIGEgc3ViY2xhc3Mgb2YgQXV0b0ZpZWxkLCBlLmcuICdkamFuZ28uZGIubW9kZWxzLkJpZ0F1dG9GaWVsZCcuXG5jb250YWN0X2J5X2Zvcm0uRmVlZGJhY2s6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZBVUxUX0FVVE9fRklFTEQgc2V0dGluZyBvciB0aGUgU3BlZWR5Q29yZUNvbnRhY3RCeUZvcm1Db25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuY29yZV9tZXNzYWdlcy5SZWFkTWFyazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlTWVzc2FnZXNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5CbG9jazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBBcHBDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5Gb2xsb3c6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZ
```

### sample[2]
```json
{
  "call_id": "OA01-M-05-django__django-13925-call-0002-f4d0c726",
  "call_index": 2,
  "cost_usd": 0.023612,
  "derived_timing": {
    "upstream_body_ms": 0.079847,
    "upstream_first_byte_ms": 8037.011451,
    "upstream_total_ms": 8037.091298
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbm1vZGVscy5XMDQyIGlzIHJhaXNlZCBvbiBpbmhlcml0ZWQgbWFudWFsbHkgc3BlY2lmaWVkIHByaW1hcnkga2V5LlxuRGVzY3JpcHRpb25cblx0XG5JIGhhdmUgbW9kZWxzIHdoaWNoIGluaGVyaXQgZnJvbSBvdGhlciBtb2RlbHMsIGFuZCB0aGV5IHNob3VsZCBpbmhlcml0IHRoZSBwcmltYXJ5IGtleS4gVGhpcyB3b3JrcyBmaW5lIHdpdGggRGphbmdvIDMuMS4gSG93ZXZlciwgaWYgSSBpbnN0YWxsIERqYW5nbyAzLjIgYWxwaGEsIHdoZW4gSSBydW4gbWFrZV9taWdyYXRpb25zIEkgZ2V0IHRoZSBmb2xsb3dpbmcgZXJyb3IgbWVzc2FnZXM6XG5TeXN0ZW0gY2hlY2sgaWRlbnRpZmllZCBzb21lIGlzc3VlczpcbldBUk5JTkdTOlxuYWNjb3VudHMuUmVzZXJ2ZWRVc2VybmFtZTogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYWNjb3VudHMuVXNlcjogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlQWNjb3VudHNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuYmxvY2tzLkJsb2NrOiAobW9kZWxzLlcwNDIpIEF1dG8tY3JlYXRlZCBwcmltYXJ5IGtleSB1c2VkIHdoZW4gbm90IGRlZmluaW5nIGEgcHJpbWFyeSBrZXkgdHlwZSwgYnkgZGVmYXVsdCAnZGphbmdvLmRiLm1vZGVscy5BdXRvRmllbGQnLlxuXHRcdEhJTlQ6IENvbmZpZ3VyZSB0aGUgREVGQVVMVF9BVVRPX0ZJRUxEIHNldHRpbmcgb3IgdGhlIEFwcENvbmZpZy5kZWZhdWx0X2F1dG9fZmllbGQgYXR0cmlidXRlIHRvIHBvaW50IHRvIGEgc3ViY2xhc3Mgb2YgQXV0b0ZpZWxkLCBlLmcuICdkamFuZ28uZGIubW9kZWxzLkJpZ0F1dG9GaWVsZCcuXG5jb250YWN0X2J5X2Zvcm0uRmVlZGJhY2s6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZBVUxUX0FVVE9fRklFTEQgc2V0dGluZyBvciB0aGUgU3BlZWR5Q29yZUNvbnRhY3RCeUZvcm1Db25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuY29yZV9tZXNzYWdlcy5SZWFkTWFyazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBTcGVlZHlDb3JlTWVzc2FnZXNDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5CbG9jazogKG1vZGVscy5XMDQyKSBBdXRvLWNyZWF0ZWQgcHJpbWFyeSBrZXkgdXNlZCB3aGVuIG5vdCBkZWZpbmluZyBhIHByaW1hcnkga2V5IHR5cGUsIGJ5IGRlZmF1bHQgJ2RqYW5nby5kYi5tb2RlbHMuQXV0b0ZpZWxkJy5cblx0XHRISU5UOiBDb25maWd1cmUgdGhlIERFRkFVTFRfQVVUT19GSUVMRCBzZXR0aW5nIG9yIHRoZSBBcHBDb25maWcuZGVmYXVsdF9hdXRvX2ZpZWxkIGF0dHJpYnV0ZSB0byBwb2ludCB0byBhIHN1YmNsYXNzIG9mIEF1dG9GaWVsZCwgZS5nLiAnZGphbmdvLmRiLm1vZGVscy5CaWdBdXRvRmllbGQnLlxuZnJpZW5kc2hpcC5Gb2xsb3c6IChtb2RlbHMuVzA0MikgQXV0by1jcmVhdGVkIHByaW1hcnkga2V5IHVzZWQgd2hlbiBub3QgZGVmaW5pbmcgYSBwcmltYXJ5IGtleSB0eXBlLCBieSBkZWZhdWx0ICdkamFuZ28uZGIubW9kZWxzLkF1dG9GaWVsZCcuXG5cdFx0SElOVDogQ29uZmlndXJlIHRoZSBERUZ
```
- `apu_characterization\out\oa01\runs\OA01-M-05-django__django-13925\raw\env_snapshots.jsonl` lines≈15 size=12537
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-32a44a4330cc4f308141798b27f0c872",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "exec_end_unix_ns": 1784226616588289500,
  "git_commit": "0c42cdf0d2422f4c080e93594d5d15381d6e955e\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:01fdabfd223571c1a567943f9f12a381dc53f8e21e4addaaa0b498bc3b8e7dfb\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226619441940400,
  "snapshot_start_unix_ns": 1784226616690103830,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-65b15f2fdb40420bb9c09a5c5d02813e",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "exec_end_unix_ns": 1784226620950459841,
  "git_commit": "0c42cdf0d2422f4c080e93594d5d15381d6e955e\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:01fdabfd223571c1a567943f9f12a381dc53f8e21e4addaaa0b498bc3b8e7dfb\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226621474347006,
  "snapshot_start_unix_ns": 1784226620955618009,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-39cbd75eea7b46a6b4cb9835ff49f582",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "exec_end_unix_ns": 1784226621667407254,
  "git_commit": "0c42cdf0d2422f4c080e93594d5d15381d6e955e\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:01fdabfd223571c1a567943f9f12a381dc53f8e21e4addaaa0b498bc3b8e7dfb\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784226622140004681,
  "snapshot_start_unix_ns": 1784226621711937865,
  "trajectory_id": "OA01-M-05-django__django-13925"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-05-django__django-13925\raw\exec_events.jsonl` lines≈34 size=25748
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ee32d914",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.django_1776_django-13925:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-de10e8d71456430eb2f35cdf81f2f522",
  "trajectory_id": "OA01-M-05-django__django-13925",
  "unix_ns": 1784226601029571231
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ee32d914",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.django_1776_django-13925:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-de10e8d71456430eb2f35cdf81f2f522",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-05-django__django-13925/raw/tool_io/exec-de10e8d71456430eb2f35cdf81f2f522.stdout_stderr.bin",
  "trajectory_id": "OA01-M-05-django__django-13925",
  "unix_ns": 1784226601322053230
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
    "bash",
    "-c",
    "ls -lR /testbed"
  ],
  "command": "bash\u0000-c\u0000ls -lR /testbed",
  "container_id": "305577b384f610afdc6b70c7e4b77d85b3e286061e5adb7e832ab854dc684fdb",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-32a44a4330cc4f308141798b27f0c872",
  "trajectory_id": "OA01-M-05-django__django-13925",
  "unix_ns": 1784226615417513145
}
```
- `apu_characterization\out\oa01\runs\OA01-M-06-sphinx-doc__sphinx-8435\derived\exec_spans.jsonl` lines≈27 size=23585
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-55c0a4fb",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8435:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 280.955871,
  "end_unix_ns": 1784227066695826805,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-9030391089cf44e3bf2de8d30020b34d",
  "start_unix_ns": 1784227066414870934,
  "timed_out": false,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
    "bash",
    "-c",
    "grep -r autodoc_type_aliases /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -r autodoc_type_aliases /testbed",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "docker_operation": "exec",
  "duration_ms": 796.692342,
  "end_unix_ns": 1784227077529186655,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-d7df1dc6cc054641864f43804f9162e4",
  "start_unix_ns": 1784227076732494313,
  "timed_out": false,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
    "bash",
    "-c",
    "grep -ri attribute /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -ri attribute /testbed",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "docker_operation": "exec",
  "duration_ms": 286.156953,
  "end_unix_ns": 1784227078051545957,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-0b0350e7d30c45b5948df61be9e1333c",
  "start_unix_ns": 1784227077765389004,
  "timed_out": false,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-06-sphinx-doc__sphinx-8435\raw\api_boundary.jsonl` lines≈50 size=6313992
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-06-sphinx-doc__sphinx-8435-call-0000-a6fec4f7",
  "call_index": 0,
  "cost_usd": 0.004654,
  "derived_timing": {
    "upstream_body_ms": 0.0,
    "upstream_first_byte_ms": 5250.374963,
    "upstream_total_ms": 5250.374963
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcbioqRGVzY3JpYmUgdGhlIGJ1ZyoqXHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcclxuXHJcbioqVG8gUmVwcm9kdWNlKipcclxuXHJcbmBgYFxyXG4jIGV4YW1wbGUucHlcclxuZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9uc1xyXG5cclxuXHJcbiM6IGJsYWggYmxhaCBibGFoXHJcbnZhcjogU3RyaW5nXHJcblxyXG5cclxuY2xhc3MgTXlTdHJpbmc6XHJcbiAgICBcIm15c3RyaW5nXCJcclxuXHJcbiAgICAjOiBibGFoIGJsYWggYmxhaFxyXG4gICAgdmFyOiBTdHJpbmdcclxuYGBgXHJcbmBgYFxyXG4jIGluZGV4LnJzdFxyXG4uLiBhdXRvbW9kdWxlOjogZXhhbXBsZVxyXG4gICA6bWVtYmVyczpcclxuICAgOnVuZG9jLW1lbWJlcnM6XHJcbmBgYFxyXG5gYGBcclxuIyBjb25mLnB5XHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzID0ge1xyXG4gICAgJ1N0cmluZyc6ICdleGFtcGxlLk15U3RyaW5nJ1xyXG59XHJcbmBgYFxyXG5cclxuKipFeHBlY3RlZCBiZWhhdmlvcioqXHJcbmBhdXRvZG9jX3R5cGVfYWxpYXNlc2Agc2hvdWxkIGJlIGFwcGxpZWQgdG8gYGV4YW1wbGUudmFyYCBhbmQgYGV4YW1wbGUuTXlTdHJpbmcudmFyYC5cclxuXHJcbioqWW91ciBwcm9qZWN0KipcclxuTi9BXHJcblxyXG4qKlNjcmVlbnNob3RzKipcclxuTi9BXHJcblxyXG4qKkVudmlyb25tZW50IGluZm8qKlxyXG4tIE9TOiBNYWNcclxuLSBQeXRob24gdmVyc2lvbjogMy45LjBcclxuLSBTcGhpbnggdmVyc2lvbjogSEVBRCBvZiAzLnggYnJhbmNoXHJcbi0gU3BoaW54IGV4dGVuc2lvbnM6IHNwaGlueC5leHQuYXV0b2RvY1xyXG4tIEV4dHJhIHRvb2xzOiBOb3RoaW5nXHJcblxyXG4qKkFkZGl0aW9uYWwgY29udGV4dCoqXHJcbk4vQVxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21tYW5kK
```

### sample[1]
```json
{
  "call_id": "OA01-M-06-sphinx-doc__sphinx-8435-call-0001-8480d975",
  "call_index": 1,
  "cost_usd": 0.015486,
  "derived_timing": {
    "upstream_body_ms": 0.131672,
    "upstream_first_byte_ms": 5610.420135,
    "upstream_total_ms": 5610.551807
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcbioqRGVzY3JpYmUgdGhlIGJ1ZyoqXHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcclxuXHJcbioqVG8gUmVwcm9kdWNlKipcclxuXHJcbmBgYFxyXG4jIGV4YW1wbGUucHlcclxuZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9uc1xyXG5cclxuXHJcbiM6IGJsYWggYmxhaCBibGFoXHJcbnZhcjogU3RyaW5nXHJcblxyXG5cclxuY2xhc3MgTXlTdHJpbmc6XHJcbiAgICBcIm15c3RyaW5nXCJcclxuXHJcbiAgICAjOiBibGFoIGJsYWggYmxhaFxyXG4gICAgdmFyOiBTdHJpbmdcclxuYGBgXHJcbmBgYFxyXG4jIGluZGV4LnJzdFxyXG4uLiBhdXRvbW9kdWxlOjogZXhhbXBsZVxyXG4gICA6bWVtYmVyczpcclxuICAgOnVuZG9jLW1lbWJlcnM6XHJcbmBgYFxyXG5gYGBcclxuIyBjb25mLnB5XHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzID0ge1xyXG4gICAgJ1N0cmluZyc6ICdleGFtcGxlLk15U3RyaW5nJ1xyXG59XHJcbmBgYFxyXG5cclxuKipFeHBlY3RlZCBiZWhhdmlvcioqXHJcbmBhdXRvZG9jX3R5cGVfYWxpYXNlc2Agc2hvdWxkIGJlIGFwcGxpZWQgdG8gYGV4YW1wbGUudmFyYCBhbmQgYGV4YW1wbGUuTXlTdHJpbmcudmFyYC5cclxuXHJcbioqWW91ciBwcm9qZWN0KipcclxuTi9BXHJcblxyXG4qKlNjcmVlbnNob3RzKipcclxuTi9BXHJcblxyXG4qKkVudmlyb25tZW50IGluZm8qKlxyXG4tIE9TOiBNYWNcclxuLSBQeXRob24gdmVyc2lvbjogMy45LjBcclxuLSBTcGhpbnggdmVyc2lvbjogSEVBRCBvZiAzLnggYnJhbmNoXHJcbi0gU3BoaW54IGV4dGVuc2lvbnM6IHNwaGlueC5leHQuYXV0b2RvY1xyXG4tIEV4dHJhIHRvb2xzOiBOb3RoaW5nXHJcblxyXG4qKkFkZGl0aW9uYWwgY29udGV4dCoqXHJcbk4vQVxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21t
```

### sample[2]
```json
{
  "call_id": "OA01-M-06-sphinx-doc__sphinx-8435-call-0002-90ca92d2",
  "call_index": 2,
  "cost_usd": 0.004928,
  "derived_timing": {
    "upstream_body_ms": 0.092852,
    "upstream_first_byte_ms": 1267.805329,
    "upstream_total_ms": 1267.898181
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcbioqRGVzY3JpYmUgdGhlIGJ1ZyoqXHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzIGRvZXMgbm90IGVmZmVjdCB0byB2YXJpYWJsZXMgYW5kIGF0dHJpYnV0ZXNcclxuXHJcbioqVG8gUmVwcm9kdWNlKipcclxuXHJcbmBgYFxyXG4jIGV4YW1wbGUucHlcclxuZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9uc1xyXG5cclxuXHJcbiM6IGJsYWggYmxhaCBibGFoXHJcbnZhcjogU3RyaW5nXHJcblxyXG5cclxuY2xhc3MgTXlTdHJpbmc6XHJcbiAgICBcIm15c3RyaW5nXCJcclxuXHJcbiAgICAjOiBibGFoIGJsYWggYmxhaFxyXG4gICAgdmFyOiBTdHJpbmdcclxuYGBgXHJcbmBgYFxyXG4jIGluZGV4LnJzdFxyXG4uLiBhdXRvbW9kdWxlOjogZXhhbXBsZVxyXG4gICA6bWVtYmVyczpcclxuICAgOnVuZG9jLW1lbWJlcnM6XHJcbmBgYFxyXG5gYGBcclxuIyBjb25mLnB5XHJcbmF1dG9kb2NfdHlwZV9hbGlhc2VzID0ge1xyXG4gICAgJ1N0cmluZyc6ICdleGFtcGxlLk15U3RyaW5nJ1xyXG59XHJcbmBgYFxyXG5cclxuKipFeHBlY3RlZCBiZWhhdmlvcioqXHJcbmBhdXRvZG9jX3R5cGVfYWxpYXNlc2Agc2hvdWxkIGJlIGFwcGxpZWQgdG8gYGV4YW1wbGUudmFyYCBhbmQgYGV4YW1wbGUuTXlTdHJpbmcudmFyYC5cclxuXHJcbioqWW91ciBwcm9qZWN0KipcclxuTi9BXHJcblxyXG4qKlNjcmVlbnNob3RzKipcclxuTi9BXHJcblxyXG4qKkVudmlyb25tZW50IGluZm8qKlxyXG4tIE9TOiBNYWNcclxuLSBQeXRob24gdmVyc2lvbjogMy45LjBcclxuLSBTcGhpbnggdmVyc2lvbjogSEVBRCBvZiAzLnggYnJhbmNoXHJcbi0gU3BoaW54IGV4dGVuc2lvbnM6IHNwaGlueC5leHQuYXV0b2RvY1xyXG4tIEV4dHJhIHRvb2xzOiBOb3RoaW5nXHJcblxyXG4qKkFkZGl0aW9uYWwgY29udGV4dCoqXHJcbk4vQVxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21t
```
- `apu_characterization\out\oa01\runs\OA01-M-06-sphinx-doc__sphinx-8435\raw\env_snapshots.jsonl` lines≈25 size=64332
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-d7df1dc6cc054641864f43804f9162e4",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "exec_end_unix_ns": 1784227077529186655,
  "git_commit": "5d8d6275a54f2c5fb72b82383b5712c22d337634\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "diff --git a/setup.py b/setup.py\nindex ca08a6d4a..21cb67b8f 100644\n--- a/setup.py\n+++ b/setup.py\n@@ -15,22 +15,22 @@ if sys.version_info < (3, 5):\n     sys.exit(1)\n \n install_requires = [\n-    'sphinxcontrib-applehelp',\n-    'sphinxcontrib-devhelp',\n+    'sphinxcontrib-applehelp<=1.0.7',\n+    'sphinxcontrib-devhelp<=1.0.5',\n     'sphinxcontrib-jsmath',\n-    'sphinxcontrib-htmlhelp',\n-    'sphinxcontrib-serializinghtml',\n-    'sphinxcontrib-qthelp',\n-    'Jinja2>=2.3',\n+    'sphinxcontrib-htmlhelp<=2.0.4',\n+    'sphinxcontrib-serializinghtml<=1.1.9',\n+    'sphinxcontrib-qthelp<=1.0.6',\n+    'Jinja2<3.0',\n     'Pygments>=2.0',\n     'docutils>=0.12',\n     'snowballstemmer>=1.1',\n     'babel>=1.3',\n-    'alabaster>=0.7,<0.8',\n+    'alabaster>=0.7,<0.7.12',\n     'imagesize',\n     'requests>=2.5.0',\n     'setuptools',\n-    'packaging',\n+    'packaging', 'markupsafe<=2.0.1',\n ]\n \n extras_require = {\ndiff --git a/tox.ini b/tox.ini\nindex dbb705a3a..9f4fc3a32 100644\n--- a/tox.ini\n+++ b/tox.ini\n@@ -28,7 +28,7 @@ setenv =\n     PYTHONWARNINGS = all,ignore::ImportWarning:importlib._bootstrap_external,ignore::DeprecationWarning:site,ignore::DeprecationWarning:distutils\n     PYTEST_ADDOPTS = {env:PYTEST_ADDOPTS:} --color yes\n commands=\n-    python -X dev -m pytest --durations 25 {posargs}\n+    python -X dev -m pytest -rA --durations 25 {posargs}\n \n [testenv:flake8]\n basepython = python3\n",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": " M setup.py\n M tox.ini\n",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:266b0ac0a7ed0aa9d909ee34e7f5b9b3312a2b7107f75d30596b92e4eed8714f\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227078015861650,
  "snapshot_start_unix_ns": 1784227077549917558,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-0b0350e7d30c45b5948df61be9e1333c",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "exec_end_unix_ns": 1784227078051545957,
  "git_commit": "5d8d6275a54f2c5fb72b82383b5712c22d337634\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "diff --git a/setup.py b/setup.py\nindex ca08a6d4a..21cb67b8f 100644\n--- a/setup.py\n+++ b/setup.py\n@@ -15,22 +15,22 @@ if sys.version_info < (3, 5):\n     sys.exit(1)\n \n install_requires = [\n-    'sphinxcontrib-applehelp',\n-    'sphinxcontrib-devhelp',\n+    'sphinxcontrib-applehelp<=1.0.7',\n+    'sphinxcontrib-devhelp<=1.0.5',\n     'sphinxcontrib-jsmath',\n-    'sphinxcontrib-htmlhelp',\n-    'sphinxcontrib-serializinghtml',\n-    'sphinxcontrib-qthelp',\n-    'Jinja2>=2.3',\n+    'sphinxcontrib-htmlhelp<=2.0.4',\n+    'sphinxcontrib-serializinghtml<=1.1.9',\n+    'sphinxcontrib-qthelp<=1.0.6',\n+    'Jinja2<3.0',\n     'Pygments>=2.0',\n     'docutils>=0.12',\n     'snowballstemmer>=1.1',\n     'babel>=1.3',\n-    'alabaster>=0.7,<0.8',\n+    'alabaster>=0.7,<0.7.12',\n     'imagesize',\n     'requests>=2.5.0',\n     'setuptools',\n-    'packaging',\n+    'packaging', 'markupsafe<=2.0.1',\n ]\n \n extras_require = {\ndiff --git a/tox.ini b/tox.ini\nindex dbb705a3a..9f4fc3a32 100644\n--- a/tox.ini\n+++ b/tox.ini\n@@ -28,7 +28,7 @@ setenv =\n     PYTHONWARNINGS = all,ignore::ImportWarning:importlib._bootstrap_external,ignore::DeprecationWarning:site,ignore::DeprecationWarning:distutils\n     PYTEST_ADDOPTS = {env:PYTEST_ADDOPTS:} --color yes\n commands=\n-    python -X dev -m pytest --durations 25 {posargs}\n+    python -X dev -m pytest -rA --durations 25 {posargs}\n \n [testenv:flake8]\n basepython = python3\n",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": " M setup.py\n M tox.ini\n",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:266b0ac0a7ed0aa9d909ee34e7f5b9b3312a2b7107f75d30596b92e4eed8714f\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227078458122006,
  "snapshot_start_unix_ns": 1784227078080032384,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-dccba61491c440a2b03da44e64638885",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "exec_end_unix_ns": 1784227078514628552,
  "git_commit": "5d8d6275a54f2c5fb72b82383b5712c22d337634\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "diff --git a/setup.py b/setup.py\nindex ca08a6d4a..21cb67b8f 100644\n--- a/setup.py\n+++ b/setup.py\n@@ -15,22 +15,22 @@ if sys.version_info < (3, 5):\n     sys.exit(1)\n \n install_requires = [\n-    'sphinxcontrib-applehelp',\n-    'sphinxcontrib-devhelp',\n+    'sphinxcontrib-applehelp<=1.0.7',\n+    'sphinxcontrib-devhelp<=1.0.5',\n     'sphinxcontrib-jsmath',\n-    'sphinxcontrib-htmlhelp',\n-    'sphinxcontrib-serializinghtml',\n-    'sphinxcontrib-qthelp',\n-    'Jinja2>=2.3',\n+    'sphinxcontrib-htmlhelp<=2.0.4',\n+    'sphinxcontrib-serializinghtml<=1.1.9',\n+    'sphinxcontrib-qthelp<=1.0.6',\n+    'Jinja2<3.0',\n     'Pygments>=2.0',\n     'docutils>=0.12',\n     'snowballstemmer>=1.1',\n     'babel>=1.3',\n-    'alabaster>=0.7,<0.8',\n+    'alabaster>=0.7,<0.7.12',\n     'imagesize',\n     'requests>=2.5.0',\n     'setuptools',\n-    'packaging',\n+    'packaging', 'markupsafe<=2.0.1',\n ]\n \n extras_require = {\ndiff --git a/tox.ini b/tox.ini\nindex dbb705a3a..9f4fc3a32 100644\n--- a/tox.ini\n+++ b/tox.ini\n@@ -28,7 +28,7 @@ setenv =\n     PYTHONWARNINGS = all,ignore::ImportWarning:importlib._bootstrap_external,ignore::DeprecationWarning:site,ignore::DeprecationWarning:distutils\n     PYTEST_ADDOPTS = {env:PYTEST_ADDOPTS:} --color yes\n commands=\n-    python -X dev -m pytest --durations 25 {posargs}\n+    python -X dev -m pytest -rA --durations 25 {posargs}\n \n [testenv:flake8]\n basepython = python3\n",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": " M setup.py\n M tox.ini\n",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:266b0ac0a7ed0aa9d909ee34e7f5b9b3312a2b7107f75d30596b92e4eed8714f\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227078923859854,
  "snapshot_start_unix_ns": 1784227078582235954,
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-06-sphinx-doc__sphinx-8435\raw\exec_events.jsonl` lines≈54 size=45253
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-55c0a4fb",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8435:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-9030391089cf44e3bf2de8d30020b34d",
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435",
  "unix_ns": 1784227066414870934
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-55c0a4fb",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8435:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-9030391089cf44e3bf2de8d30020b34d",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-06-sphinx-doc__sphinx-8435/raw/tool_io/exec-9030391089cf44e3bf2de8d30020b34d.stdout_stderr.bin",
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435",
  "unix_ns": 1784227066695826805
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
    "bash",
    "-c",
    "grep -r autodoc_type_aliases /testbed"
  ],
  "command": "bash\u0000-c\u0000grep -r autodoc_type_aliases /testbed",
  "container_id": "a38ca21c8b2704a2fd2f2fb4240df631a555b895fead0f65d50a796b60a06e72",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-d7df1dc6cc054641864f43804f9162e4",
  "trajectory_id": "OA01-M-06-sphinx-doc__sphinx-8435",
  "unix_ns": 1784227076732494313
}
```
- `apu_characterization\out\oa01\runs\OA01-M-07-mwaskom__seaborn-3407\derived\exec_spans.jsonl` lines≈16 size=13207
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-c13f266d",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.mwaskom_1776_seaborn-3407:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 449.685528,
  "end_unix_ns": 1784227660995750076,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-b126a7aa9d2a468a8b375725825c251c",
  "start_unix_ns": 1784227660546064548,
  "timed_out": false,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
    "bash",
    "-c",
    "ls -l"
  ],
  "command": "bash\u0000-c\u0000ls -l",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "docker_operation": "exec",
  "duration_ms": 314.903855,
  "end_unix_ns": 1784227685126048447,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-a67f9a1962e3416090316f705dd4abf4",
  "start_unix_ns": 1784227684811144592,
  "timed_out": false,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
    "bash",
    "-c",
    "grep -r 'def pairplot' ."
  ],
  "command": "bash\u0000-c\u0000grep -r 'def pairplot' .",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "docker_operation": "exec",
  "duration_ms": 290.216567,
  "end_unix_ns": 1784227685601782095,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-92e9b7d777bd4106b7c761d1fdfc2c84",
  "start_unix_ns": 1784227685311565528,
  "timed_out": false,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-07-mwaskom__seaborn-3407\raw\api_boundary.jsonl` lines≈22 size=1310598
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-07-mwaskom__seaborn-3407-call-0000-7a213337",
  "call_index": 0,
  "cost_usd": 0.005734,
  "derived_timing": {
    "upstream_body_ms": 0.084829,
    "upstream_first_byte_ms": 6448.6506,
    "upstream_total_ms": 6448.735429
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnBhaXJwbG90IHJhaXNlcyBLZXlFcnJvciB3aXRoIE11bHRpSW5kZXggRGF0YUZyYW1lXG5XaGVuIHRyeWluZyB0byBwYWlycGxvdCBhIE11bHRpSW5kZXggRGF0YUZyYW1lLCBgcGFpcnBsb3RgIHJhaXNlcyBhIGBLZXlFcnJvcmA6XHJcblxyXG5NUkU6XHJcblxyXG5gYGBweXRob25cclxuaW1wb3J0IG51bXB5IGFzIG5wXHJcbmltcG9ydCBwYW5kYXMgYXMgcGRcclxuaW1wb3J0IHNlYWJvcm4gYXMgc25zXHJcblxyXG5cclxuZGF0YSA9IHtcclxuICAgIChcIkFcIiwgXCIxXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG4gICAgKFwiQVwiLCBcIjJcIik6IG5wLnJhbmRvbS5yYW5kKDEwMCksXHJcbiAgICAoXCJCXCIsIFwiMVwiKTogbnAucmFuZG9tLnJhbmQoMTAwKSxcclxuICAgIChcIkJcIiwgXCIyXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG59XHJcbmRmID0gcGQuRGF0YUZyYW1lKGRhdGEpXHJcbnNucy5wYWlycGxvdChkZilcclxuYGBgXHJcblxyXG5PdXRwdXQ6XHJcblxyXG5gYGBcclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIHBhaXJwbG90KGRhdGEsIGh1ZSwgaHVlX29yZGVyLCBwYWxldHRlLCB2YXJzLCB4X3ZhcnMsIHlfdmFycywga2luZCwgZGlhZ19raW5kLCBtYXJrZXJzLCBoZWlnaHQsIGFzcGVjdCwgY29ybmVyLCBkcm9wbmEsIHBsb3Rfa3dzLCBkaWFnX2t3cywgZ3JpZF9rd3MsIHNpemUpXHJcbiAgIDIxNDIgICAgIGRpYWdfa3dzLnNldGRlZmF1bHQoXCJsZWdlbmRcIiwgRmFsc2UpXHJcbiAgIDIxNDMgICAgIGlmIGRpYWdfa2luZCA9PSBcImhpc3RcIjpcclxuLT4gMjE0NCAgICAgICAgIGdyaWQubWFwX2RpYWcoaGlzdHBsb3QsICoqZGlhZ19rd3MpXHJcbiAgIDIxNDUgICAgIGVsaWYgZGlhZ19raW5kID09IFwia2RlXCI6XHJcbiAgIDIxNDYgICAgICAgICBkaWFnX2t3cy5zZXRkZWZhdWx0KFwiZmlsbFwiLCBUcnVlKVxyXG5cclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIG1hcF9kaWFnKHNlbGYsIGZ1bmMsICoqa3dhcmdzKVxyXG4gICAxNDg4ICAgICAgICAgICAgICAgICBwbHQuc2NhKGF4KVxyXG4gICAxNDg5IFxyXG4tPiAxNDkwICAgICAgICAgICAgIHZlY3RvciA9IHNlbGYuZGF0YVt2YXJdXHJcbiAgIDE0OTEgICAgICAgICAgICAgaWYgc2VsZi5faHVlX3ZhciBpcyBub3QgTm9uZTpcclxuICAgMTQ5MiAgICAgICAgICAgICAgICAgaHVlID0gc2VsZi5kYXRhW3NlbGYuX2h1ZV92YXJdXHJcblxyXG5bYzpcXFVzZXJzXFxLTHV1XFxhbmFjb25kYTNcXGxpYlxcc2l0ZS1wYWNrYWdlc1xccGFuZGFzXFxjb3JlXFxmcmFtZS5weV0oZmlsZTovLy9DOi9Vc2Vycy9LTHV1L2FuYWNvbmRhMy9saWIvc2l0ZS1wYWNrYWdlcy9wYW5kYXMvY29yZS9mcmFtZS5weSkgaW4gX19nZXRpdGVtX18oc2VsZiwga2V5KVxyXG4gICAzNzY1ICAgICAgICAgICAgIGlmIGlzX2l0ZXJhdG9yKGtleSk6XHJcbiAgIDM3NjYgICAgICAgICAgICAgICAgIGtleSA9IGxpc3Qoa2V5KVxyXG4tPiAzNzY3ICAgICAgICAgICAgIGluZGV4ZXIgPSBzZWxmLmNvbHVtbnMuX2dldF9pbmRleGVyX3N0cmljdChrZXksIFwiY29sdW1uc1wiKVsxXVxyXG4gICAzNzY4IFxyXG4gICAzNzY5ICAgICAgICAgIyB0YWtlKCkgZG9lcyBub3QgYWNjZXB0IGJvb2xlYW4gaW5kZXhlcnNcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9nZXRfaW5kZXhlcl9zdHJpY3Qoc2VsZiwga2V5LCBheGlzX25hbWUpXHJcbiAgIDI1MzQgICAgICAgICAgICAgaW5kZXhlciA9IHNlbGYuX2dldF9pbmRleGVyX2xldmVsXzAoa2V5YXJyKVxyXG4gICAyNTM1IFxyXG4tPiAyNTM2ICAgICAgICAgICAgIHNlbGYuX3JhaXNlX2lmX21pc3Npbmcoa2V5LCBpbmRleGVyLCBheGlzX25hbWUpXHJcbiAgIDI1MzcgICAgICAgICAgICAgcmV0dXJuIHNlbGZbaW5kZXhlcl0sIGluZGV4ZXJcclxuICAgMjUzOCBcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9yYWlzZV9pZl9taXNzaW5nKHNl
```

### sample[1]
```json
{
  "call_id": "OA01-M-07-mwaskom__seaborn-3407-call-0001-4610f080",
  "call_index": 1,
  "cost_usd": 0.003082,
  "derived_timing": {
    "upstream_body_ms": 0.0,
    "upstream_first_byte_ms": 6664.698111,
    "upstream_total_ms": 6664.698111
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnBhaXJwbG90IHJhaXNlcyBLZXlFcnJvciB3aXRoIE11bHRpSW5kZXggRGF0YUZyYW1lXG5XaGVuIHRyeWluZyB0byBwYWlycGxvdCBhIE11bHRpSW5kZXggRGF0YUZyYW1lLCBgcGFpcnBsb3RgIHJhaXNlcyBhIGBLZXlFcnJvcmA6XHJcblxyXG5NUkU6XHJcblxyXG5gYGBweXRob25cclxuaW1wb3J0IG51bXB5IGFzIG5wXHJcbmltcG9ydCBwYW5kYXMgYXMgcGRcclxuaW1wb3J0IHNlYWJvcm4gYXMgc25zXHJcblxyXG5cclxuZGF0YSA9IHtcclxuICAgIChcIkFcIiwgXCIxXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG4gICAgKFwiQVwiLCBcIjJcIik6IG5wLnJhbmRvbS5yYW5kKDEwMCksXHJcbiAgICAoXCJCXCIsIFwiMVwiKTogbnAucmFuZG9tLnJhbmQoMTAwKSxcclxuICAgIChcIkJcIiwgXCIyXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG59XHJcbmRmID0gcGQuRGF0YUZyYW1lKGRhdGEpXHJcbnNucy5wYWlycGxvdChkZilcclxuYGBgXHJcblxyXG5PdXRwdXQ6XHJcblxyXG5gYGBcclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIHBhaXJwbG90KGRhdGEsIGh1ZSwgaHVlX29yZGVyLCBwYWxldHRlLCB2YXJzLCB4X3ZhcnMsIHlfdmFycywga2luZCwgZGlhZ19raW5kLCBtYXJrZXJzLCBoZWlnaHQsIGFzcGVjdCwgY29ybmVyLCBkcm9wbmEsIHBsb3Rfa3dzLCBkaWFnX2t3cywgZ3JpZF9rd3MsIHNpemUpXHJcbiAgIDIxNDIgICAgIGRpYWdfa3dzLnNldGRlZmF1bHQoXCJsZWdlbmRcIiwgRmFsc2UpXHJcbiAgIDIxNDMgICAgIGlmIGRpYWdfa2luZCA9PSBcImhpc3RcIjpcclxuLT4gMjE0NCAgICAgICAgIGdyaWQubWFwX2RpYWcoaGlzdHBsb3QsICoqZGlhZ19rd3MpXHJcbiAgIDIxNDUgICAgIGVsaWYgZGlhZ19raW5kID09IFwia2RlXCI6XHJcbiAgIDIxNDYgICAgICAgICBkaWFnX2t3cy5zZXRkZWZhdWx0KFwiZmlsbFwiLCBUcnVlKVxyXG5cclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIG1hcF9kaWFnKHNlbGYsIGZ1bmMsICoqa3dhcmdzKVxyXG4gICAxNDg4ICAgICAgICAgICAgICAgICBwbHQuc2NhKGF4KVxyXG4gICAxNDg5IFxyXG4tPiAxNDkwICAgICAgICAgICAgIHZlY3RvciA9IHNlbGYuZGF0YVt2YXJdXHJcbiAgIDE0OTEgICAgICAgICAgICAgaWYgc2VsZi5faHVlX3ZhciBpcyBub3QgTm9uZTpcclxuICAgMTQ5MiAgICAgICAgICAgICAgICAgaHVlID0gc2VsZi5kYXRhW3NlbGYuX2h1ZV92YXJdXHJcblxyXG5bYzpcXFVzZXJzXFxLTHV1XFxhbmFjb25kYTNcXGxpYlxcc2l0ZS1wYWNrYWdlc1xccGFuZGFzXFxjb3JlXFxmcmFtZS5weV0oZmlsZTovLy9DOi9Vc2Vycy9LTHV1L2FuYWNvbmRhMy9saWIvc2l0ZS1wYWNrYWdlcy9wYW5kYXMvY29yZS9mcmFtZS5weSkgaW4gX19nZXRpdGVtX18oc2VsZiwga2V5KVxyXG4gICAzNzY1ICAgICAgICAgICAgIGlmIGlzX2l0ZXJhdG9yKGtleSk6XHJcbiAgIDM3NjYgICAgICAgICAgICAgICAgIGtleSA9IGxpc3Qoa2V5KVxyXG4tPiAzNzY3ICAgICAgICAgICAgIGluZGV4ZXIgPSBzZWxmLmNvbHVtbnMuX2dldF9pbmRleGVyX3N0cmljdChrZXksIFwiY29sdW1uc1wiKVsxXVxyXG4gICAzNzY4IFxyXG4gICAzNzY5ICAgICAgICAgIyB0YWtlKCkgZG9lcyBub3QgYWNjZXB0IGJvb2xlYW4gaW5kZXhlcnNcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9nZXRfaW5kZXhlcl9zdHJpY3Qoc2VsZiwga2V5LCBheGlzX25hbWUpXHJcbiAgIDI1MzQgICAgICAgICAgICAgaW5kZXhlciA9IHNlbGYuX2dldF9pbmRleGVyX2xldmVsXzAoa2V5YXJyKVxyXG4gICAyNTM1IFxyXG4tPiAyNTM2ICAgICAgICAgICAgIHNlbGYuX3JhaXNlX2lmX21pc3Npbmcoa2V5LCBpbmRleGVyLCBheGlzX25hbWUpXHJcbiAgIDI1MzcgICAgICAgICAgICAgcmV0dXJuIHNlbGZbaW5kZXhlcl0sIGluZGV4ZXJcclxuICAgMjUzOCBcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9yYWlzZV9pZl9taXNzaW5nKHNlbGY
```

### sample[2]
```json
{
  "call_id": "OA01-M-07-mwaskom__seaborn-3407-call-0002-4f477b48",
  "call_index": 2,
  "cost_usd": 0.002814,
  "derived_timing": {
    "upstream_body_ms": 0.165321,
    "upstream_first_byte_ms": 5953.344647,
    "upstream_total_ms": 5953.509968
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnBhaXJwbG90IHJhaXNlcyBLZXlFcnJvciB3aXRoIE11bHRpSW5kZXggRGF0YUZyYW1lXG5XaGVuIHRyeWluZyB0byBwYWlycGxvdCBhIE11bHRpSW5kZXggRGF0YUZyYW1lLCBgcGFpcnBsb3RgIHJhaXNlcyBhIGBLZXlFcnJvcmA6XHJcblxyXG5NUkU6XHJcblxyXG5gYGBweXRob25cclxuaW1wb3J0IG51bXB5IGFzIG5wXHJcbmltcG9ydCBwYW5kYXMgYXMgcGRcclxuaW1wb3J0IHNlYWJvcm4gYXMgc25zXHJcblxyXG5cclxuZGF0YSA9IHtcclxuICAgIChcIkFcIiwgXCIxXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG4gICAgKFwiQVwiLCBcIjJcIik6IG5wLnJhbmRvbS5yYW5kKDEwMCksXHJcbiAgICAoXCJCXCIsIFwiMVwiKTogbnAucmFuZG9tLnJhbmQoMTAwKSxcclxuICAgIChcIkJcIiwgXCIyXCIpOiBucC5yYW5kb20ucmFuZCgxMDApLFxyXG59XHJcbmRmID0gcGQuRGF0YUZyYW1lKGRhdGEpXHJcbnNucy5wYWlycGxvdChkZilcclxuYGBgXHJcblxyXG5PdXRwdXQ6XHJcblxyXG5gYGBcclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIHBhaXJwbG90KGRhdGEsIGh1ZSwgaHVlX29yZGVyLCBwYWxldHRlLCB2YXJzLCB4X3ZhcnMsIHlfdmFycywga2luZCwgZGlhZ19raW5kLCBtYXJrZXJzLCBoZWlnaHQsIGFzcGVjdCwgY29ybmVyLCBkcm9wbmEsIHBsb3Rfa3dzLCBkaWFnX2t3cywgZ3JpZF9rd3MsIHNpemUpXHJcbiAgIDIxNDIgICAgIGRpYWdfa3dzLnNldGRlZmF1bHQoXCJsZWdlbmRcIiwgRmFsc2UpXHJcbiAgIDIxNDMgICAgIGlmIGRpYWdfa2luZCA9PSBcImhpc3RcIjpcclxuLT4gMjE0NCAgICAgICAgIGdyaWQubWFwX2RpYWcoaGlzdHBsb3QsICoqZGlhZ19rd3MpXHJcbiAgIDIxNDUgICAgIGVsaWYgZGlhZ19raW5kID09IFwia2RlXCI6XHJcbiAgIDIxNDYgICAgICAgICBkaWFnX2t3cy5zZXRkZWZhdWx0KFwiZmlsbFwiLCBUcnVlKVxyXG5cclxuW2M6XFxVc2Vyc1xcS0x1dVxcYW5hY29uZGEzXFxsaWJcXHNpdGUtcGFja2FnZXNcXHNlYWJvcm5cXGF4aXNncmlkLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3NlYWJvcm4vYXhpc2dyaWQucHkpIGluIG1hcF9kaWFnKHNlbGYsIGZ1bmMsICoqa3dhcmdzKVxyXG4gICAxNDg4ICAgICAgICAgICAgICAgICBwbHQuc2NhKGF4KVxyXG4gICAxNDg5IFxyXG4tPiAxNDkwICAgICAgICAgICAgIHZlY3RvciA9IHNlbGYuZGF0YVt2YXJdXHJcbiAgIDE0OTEgICAgICAgICAgICAgaWYgc2VsZi5faHVlX3ZhciBpcyBub3QgTm9uZTpcclxuICAgMTQ5MiAgICAgICAgICAgICAgICAgaHVlID0gc2VsZi5kYXRhW3NlbGYuX2h1ZV92YXJdXHJcblxyXG5bYzpcXFVzZXJzXFxLTHV1XFxhbmFjb25kYTNcXGxpYlxcc2l0ZS1wYWNrYWdlc1xccGFuZGFzXFxjb3JlXFxmcmFtZS5weV0oZmlsZTovLy9DOi9Vc2Vycy9LTHV1L2FuYWNvbmRhMy9saWIvc2l0ZS1wYWNrYWdlcy9wYW5kYXMvY29yZS9mcmFtZS5weSkgaW4gX19nZXRpdGVtX18oc2VsZiwga2V5KVxyXG4gICAzNzY1ICAgICAgICAgICAgIGlmIGlzX2l0ZXJhdG9yKGtleSk6XHJcbiAgIDM3NjYgICAgICAgICAgICAgICAgIGtleSA9IGxpc3Qoa2V5KVxyXG4tPiAzNzY3ICAgICAgICAgICAgIGluZGV4ZXIgPSBzZWxmLmNvbHVtbnMuX2dldF9pbmRleGVyX3N0cmljdChrZXksIFwiY29sdW1uc1wiKVsxXVxyXG4gICAzNzY4IFxyXG4gICAzNzY5ICAgICAgICAgIyB0YWtlKCkgZG9lcyBub3QgYWNjZXB0IGJvb2xlYW4gaW5kZXhlcnNcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9nZXRfaW5kZXhlcl9zdHJpY3Qoc2VsZiwga2V5LCBheGlzX25hbWUpXHJcbiAgIDI1MzQgICAgICAgICAgICAgaW5kZXhlciA9IHNlbGYuX2dldF9pbmRleGVyX2xldmVsXzAoa2V5YXJyKVxyXG4gICAyNTM1IFxyXG4tPiAyNTM2ICAgICAgICAgICAgIHNlbGYuX3JhaXNlX2lmX21pc3Npbmcoa2V5LCBpbmRleGVyLCBheGlzX25hbWUpXHJcbiAgIDI1MzcgICAgICAgICAgICAgcmV0dXJuIHNlbGZbaW5kZXhlcl0sIGluZGV4ZXJcclxuICAgMjUzOCBcclxuXHJcbltjOlxcVXNlcnNcXEtMdXVcXGFuYWNvbmRhM1xcbGliXFxzaXRlLXBhY2thZ2VzXFxwYW5kYXNcXGNvcmVcXGluZGV4ZXNcXG11bHRpLnB5XShmaWxlOi8vL0M6L1VzZXJzL0tMdXUvYW5hY29uZGEzL2xpYi9zaXRlLXBhY2thZ2VzL3BhbmRhcy9jb3JlL2luZGV4ZXMvbXVsdGkucHkpIGluIF9yYWlzZV9pZl9taXNzaW5nKH
```
- `apu_characterization\out\oa01\runs\OA01-M-07-mwaskom__seaborn-3407\raw\env_snapshots.jsonl` lines≈14 size=15103
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-a67f9a1962e3416090316f705dd4abf4",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "exec_end_unix_ns": 1784227685126048447,
  "git_commit": "515286e02be3e4c0ff2ef4addb34a53c4a676ee4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:bb9684f4e1f696474c01eda40ac43d0ccae1e2bd0ba4e3c5f62ea3bb1acb2012\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227685685354476,
  "snapshot_start_unix_ns": 1784227685182192270,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-92e9b7d777bd4106b7c761d1fdfc2c84",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "exec_end_unix_ns": 1784227685601782095,
  "git_commit": "515286e02be3e4c0ff2ef4addb34a53c4a676ee4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:bb9684f4e1f696474c01eda40ac43d0ccae1e2bd0ba4e3c5f62ea3bb1acb2012\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227686095620083,
  "snapshot_start_unix_ns": 1784227685769017134,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-378ebd15ff9e45dca61e724801078756",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "exec_end_unix_ns": 1784227698055768779,
  "git_commit": "515286e02be3e4c0ff2ef4addb34a53c4a676ee4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:bb9684f4e1f696474c01eda40ac43d0ccae1e2bd0ba4e3c5f62ea3bb1acb2012\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227698411749462,
  "snapshot_start_unix_ns": 1784227698101441756,
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-07-mwaskom__seaborn-3407\raw\exec_events.jsonl` lines≈32 size=25268
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-c13f266d",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.mwaskom_1776_seaborn-3407:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-b126a7aa9d2a468a8b375725825c251c",
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407",
  "unix_ns": 1784227660546064548
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-c13f266d",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.mwaskom_1776_seaborn-3407:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-b126a7aa9d2a468a8b375725825c251c",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-07-mwaskom__seaborn-3407/raw/tool_io/exec-b126a7aa9d2a468a8b375725825c251c.stdout_stderr.bin",
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407",
  "unix_ns": 1784227660995750076
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
    "bash",
    "-c",
    "ls -l"
  ],
  "command": "bash\u0000-c\u0000ls -l",
  "container_id": "1dad1a7ce2cab14f218d9c01237b2064ba239f6ca9c9c83cb25affa448b71df4",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-a67f9a1962e3416090316f705dd4abf4",
  "trajectory_id": "OA01-M-07-mwaskom__seaborn-3407",
  "unix_ns": 1784227684811144592
}
```
- `apu_characterization\out\oa01\runs\OA01-M-08-pylint-dev__pylint-7228\derived\exec_spans.jsonl` lines≈15 size=15429
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-defac22a",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-7228:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 369.98123,
  "end_unix_ns": 1784227869925584291,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-aaae5f4e149d40eab01b7ba9f207bf92",
  "start_unix_ns": 1784227869555603061,
  "timed_out": false,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
    "bash",
    "-c",
    "grep -r \"function-rgx\" ."
  ],
  "command": "bash\u0000-c\u0000grep -r \"function-rgx\" .",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "docker_operation": "exec",
  "duration_ms": 1115.740098,
  "end_unix_ns": 1784227885582497675,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-5875cd969af5428587e3de59a59607b4",
  "start_unix_ns": 1784227884466757577,
  "timed_out": false,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
    "bash",
    "-c",
    "grep -r \"re.compile\" ."
  ],
  "command": "bash\u0000-c\u0000grep -r \"re.compile\" .",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "docker_operation": "exec",
  "duration_ms": 343.500088,
  "end_unix_ns": 1784227886084067973,
  "flags": [],
  "returncode": 2,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-0d2d8e56a0c948618da7e6757a3db9b6",
  "start_unix_ns": 1784227885740567885,
  "timed_out": false,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-08-pylint-dev__pylint-7228\raw\api_boundary.jsonl` lines≈19 size=1945317
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-08-pylint-dev__pylint-7228-call-0000-f8676170",
  "call_index": 0,
  "cost_usd": 0.008124,
  "derived_timing": {
    "upstream_body_ms": 0.051335,
    "upstream_first_byte_ms": 9689.426035,
    "upstream_total_ms": 9689.47737
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnJ4ZyBpbmNsdWRlICdcXHB7SGFufScgd2lsbCB0aHJvdyBlcnJvclxuIyMjIEJ1ZyBkZXNjcmlwdGlvblxyXG5cclxuY29uZmlnIHJ4ZyBpbiBweWxpbnRyYyB3aXRoIFxccHtIYW59IHdpbGwgdGhyb3cgZXJyXHJcblxyXG4jIyMgQ29uZmlndXJhdGlvblxyXG4ucHlsaW50cmM6XHJcblxyXG5gYGBpbmlcclxuZnVuY3Rpb24tcmd4PVtcXHB7SGFufWEtel9dW1xccHtIYW59YS16MC05X117MiwzMH0kXHJcbmBgYFxyXG5cclxuIyMjIENvbW1hbmQgdXNlZFxyXG5cclxuYGBgc2hlbGxcclxucHlsaW50XHJcbmBgYFxyXG5cclxuXHJcbiMjIyBQeWxpbnQgb3V0cHV0XHJcblxyXG5gYGBzaGVsbFxyXG4odmVudnRlc3QpIHRzdW5nLWhhbmRlLU1hY0Jvb2stUHJvOnJvYm90X2lzX2NvbW1pbmcgdHN1bmctaGFuJCBweWxpbnRcclxuVHJhY2ViYWNrIChtb3N0IHJlY2VudCBjYWxsIGxhc3QpOlxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2Jpbi9weWxpbnRcIiwgbGluZSA4LCBpbiA8bW9kdWxlPlxyXG4gICAgc3lzLmV4aXQocnVuX3B5bGludCgpKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvX19pbml0X18ucHlcIiwgbGluZSAyNSwgaW4gcnVuX3B5bGludFxyXG4gICAgUHlsaW50UnVuKGFyZ3Ygb3Igc3lzLmFyZ3ZbMTpdKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvbGludC9ydW4ucHlcIiwgbGluZSAxNjEsIGluIF9faW5pdF9fXHJcbiAgICBhcmdzID0gX2NvbmZpZ19pbml0aWFsaXphdGlvbihcclxuICBGaWxlIFwiL1VzZXJzL3RzdW5nLWhhbi9QeWNoYXJtUHJvamVjdHMvcm9ib3RfaXNfY29tbWluZy92ZW52dGVzdC9saWIvcHl0aG9uMy45L3NpdGUtcGFja2FnZXMvcHlsaW50L2NvbmZpZy9jb25maWdfaW5pdGlhbGl6YXRpb24ucHlcIiwgbGluZSA1NywgaW4gX2NvbmZpZ19pbml0aWFsaXphdGlvblxyXG4gICAgbGludGVyLl9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGUoY29uZmlnX2FyZ3MpXHJcbiAgRmlsZSBcIi9Vc2Vycy90c3VuZy1oYW4vUHljaGFybVByb2plY3RzL3JvYm90X2lzX2NvbW1pbmcvdmVudnRlc3QvbGliL3B5dGhvbjMuOS9zaXRlLXBhY2thZ2VzL3B5bGludC9jb25maWcvYXJndW1lbnRzX21hbmFnZXIucHlcIiwgbGluZSAyNDQsIGluIF9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGVcclxuICAgIHNlbGYuY29uZmlnLCBwYXJzZWRfYXJncyA9IHNlbGYuX2FyZ19wYXJzZXIucGFyc2Vfa25vd25fYXJncyhcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxODU4LCBpbiBwYXJzZV9rbm93bl9hcmdzXHJcbiAgICBuYW1lc3BhY2UsIGFyZ3MgPSBzZWxmLl9wYXJzZV9rbm93bl9hcmdzKGFyZ3MsIG5hbWVzcGFjZSlcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAyMDY3LCBpbiBfcGFyc2Vfa25vd25fYXJnc1xyXG4gICAgc3RhcnRfaW5kZXggPSBjb25zdW1lX29wdGlvbmFsKHN0YXJ0X2luZGV4KVxyXG4gIEZpbGUgXCIvdXNyL2xvY2FsL0NlbGxhci9weXRob25AMy45LzMuOS4xM18xL0ZyYW1ld29ya3MvUHl0aG9uLmZyYW1ld29yay9WZXJzaW9ucy8zLjkvbGliL3B5dGhvbjMuOS9hcmdwYXJzZS5weVwiLCBsaW5lIDIwMDcsIGluIGNvbnN1bWVfb3B0aW9uYWxcclxuICAgIHRha2VfYWN0aW9uKGFjdGlvbiwgYXJncywgb3B0aW9uX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxOTE5LCBpbiB0YWtlX2FjdGlvblxyXG4gICAgYXJndW1lbnRfdmFsdWVzID0gc2VsZi5fZ2V0X3ZhbHVlcyhhY3Rpb24sIGFyZ3VtZW50X3N0cmluZ3MpXHJcbiAgRmlsZSBcIi91c3IvbG9jYWwvQ2VsbGFyL3B5dGhvbkAzLjkvMy45LjEzXzEvRnJhbWV3b3Jrcy9QeXRob24uZnJhbWV3b3JrL1ZlcnNpb25zLzMuOS9saWIvcHl0aG9uMy45L2FyZ3BhcnNlLnB5XCIsIGxpbmUgMjQ1MCwgaW4gX2dldF92YWx1ZXNcclxuICAgIHZhbHVlID0gc2VsZi5fZ2V0X3ZhbHVlKGFjdGlvbiwgYXJnX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfM
```

### sample[1]
```json
{
  "call_id": "OA01-M-08-pylint-dev__pylint-7228-call-0001-ce8cbcc6",
  "call_index": 1,
  "cost_usd": 0.012014,
  "derived_timing": {
    "upstream_body_ms": 0.073405,
    "upstream_first_byte_ms": 8006.694202,
    "upstream_total_ms": 8006.767607
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnJ4ZyBpbmNsdWRlICdcXHB7SGFufScgd2lsbCB0aHJvdyBlcnJvclxuIyMjIEJ1ZyBkZXNjcmlwdGlvblxyXG5cclxuY29uZmlnIHJ4ZyBpbiBweWxpbnRyYyB3aXRoIFxccHtIYW59IHdpbGwgdGhyb3cgZXJyXHJcblxyXG4jIyMgQ29uZmlndXJhdGlvblxyXG4ucHlsaW50cmM6XHJcblxyXG5gYGBpbmlcclxuZnVuY3Rpb24tcmd4PVtcXHB7SGFufWEtel9dW1xccHtIYW59YS16MC05X117MiwzMH0kXHJcbmBgYFxyXG5cclxuIyMjIENvbW1hbmQgdXNlZFxyXG5cclxuYGBgc2hlbGxcclxucHlsaW50XHJcbmBgYFxyXG5cclxuXHJcbiMjIyBQeWxpbnQgb3V0cHV0XHJcblxyXG5gYGBzaGVsbFxyXG4odmVudnRlc3QpIHRzdW5nLWhhbmRlLU1hY0Jvb2stUHJvOnJvYm90X2lzX2NvbW1pbmcgdHN1bmctaGFuJCBweWxpbnRcclxuVHJhY2ViYWNrIChtb3N0IHJlY2VudCBjYWxsIGxhc3QpOlxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2Jpbi9weWxpbnRcIiwgbGluZSA4LCBpbiA8bW9kdWxlPlxyXG4gICAgc3lzLmV4aXQocnVuX3B5bGludCgpKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvX19pbml0X18ucHlcIiwgbGluZSAyNSwgaW4gcnVuX3B5bGludFxyXG4gICAgUHlsaW50UnVuKGFyZ3Ygb3Igc3lzLmFyZ3ZbMTpdKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvbGludC9ydW4ucHlcIiwgbGluZSAxNjEsIGluIF9faW5pdF9fXHJcbiAgICBhcmdzID0gX2NvbmZpZ19pbml0aWFsaXphdGlvbihcclxuICBGaWxlIFwiL1VzZXJzL3RzdW5nLWhhbi9QeWNoYXJtUHJvamVjdHMvcm9ib3RfaXNfY29tbWluZy92ZW52dGVzdC9saWIvcHl0aG9uMy45L3NpdGUtcGFja2FnZXMvcHlsaW50L2NvbmZpZy9jb25maWdfaW5pdGlhbGl6YXRpb24ucHlcIiwgbGluZSA1NywgaW4gX2NvbmZpZ19pbml0aWFsaXphdGlvblxyXG4gICAgbGludGVyLl9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGUoY29uZmlnX2FyZ3MpXHJcbiAgRmlsZSBcIi9Vc2Vycy90c3VuZy1oYW4vUHljaGFybVByb2plY3RzL3JvYm90X2lzX2NvbW1pbmcvdmVudnRlc3QvbGliL3B5dGhvbjMuOS9zaXRlLXBhY2thZ2VzL3B5bGludC9jb25maWcvYXJndW1lbnRzX21hbmFnZXIucHlcIiwgbGluZSAyNDQsIGluIF9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGVcclxuICAgIHNlbGYuY29uZmlnLCBwYXJzZWRfYXJncyA9IHNlbGYuX2FyZ19wYXJzZXIucGFyc2Vfa25vd25fYXJncyhcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxODU4LCBpbiBwYXJzZV9rbm93bl9hcmdzXHJcbiAgICBuYW1lc3BhY2UsIGFyZ3MgPSBzZWxmLl9wYXJzZV9rbm93bl9hcmdzKGFyZ3MsIG5hbWVzcGFjZSlcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAyMDY3LCBpbiBfcGFyc2Vfa25vd25fYXJnc1xyXG4gICAgc3RhcnRfaW5kZXggPSBjb25zdW1lX29wdGlvbmFsKHN0YXJ0X2luZGV4KVxyXG4gIEZpbGUgXCIvdXNyL2xvY2FsL0NlbGxhci9weXRob25AMy45LzMuOS4xM18xL0ZyYW1ld29ya3MvUHl0aG9uLmZyYW1ld29yay9WZXJzaW9ucy8zLjkvbGliL3B5dGhvbjMuOS9hcmdwYXJzZS5weVwiLCBsaW5lIDIwMDcsIGluIGNvbnN1bWVfb3B0aW9uYWxcclxuICAgIHRha2VfYWN0aW9uKGFjdGlvbiwgYXJncywgb3B0aW9uX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxOTE5LCBpbiB0YWtlX2FjdGlvblxyXG4gICAgYXJndW1lbnRfdmFsdWVzID0gc2VsZi5fZ2V0X3ZhbHVlcyhhY3Rpb24sIGFyZ3VtZW50X3N0cmluZ3MpXHJcbiAgRmlsZSBcIi91c3IvbG9jYWwvQ2VsbGFyL3B5dGhvbkAzLjkvMy45LjEzXzEvRnJhbWV3b3Jrcy9QeXRob24uZnJhbWV3b3JrL1ZlcnNpb25zLzMuOS9saWIvcHl0aG9uMy45L2FyZ3BhcnNlLnB5XCIsIGxpbmUgMjQ1MCwgaW4gX2dldF92YWx1ZXNcclxuICAgIHZhbHVlID0gc2VsZi5fZ2V0X3ZhbHVlKGFjdGlvbiwgYXJnX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNf
```

### sample[2]
```json
{
  "call_id": "OA01-M-08-pylint-dev__pylint-7228-call-0002-23ef5d86",
  "call_index": 2,
  "cost_usd": 0.010428,
  "derived_timing": {
    "upstream_body_ms": 0.157409,
    "upstream_first_byte_ms": 6067.137252,
    "upstream_total_ms": 6067.294661
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbnJ4ZyBpbmNsdWRlICdcXHB7SGFufScgd2lsbCB0aHJvdyBlcnJvclxuIyMjIEJ1ZyBkZXNjcmlwdGlvblxyXG5cclxuY29uZmlnIHJ4ZyBpbiBweWxpbnRyYyB3aXRoIFxccHtIYW59IHdpbGwgdGhyb3cgZXJyXHJcblxyXG4jIyMgQ29uZmlndXJhdGlvblxyXG4ucHlsaW50cmM6XHJcblxyXG5gYGBpbmlcclxuZnVuY3Rpb24tcmd4PVtcXHB7SGFufWEtel9dW1xccHtIYW59YS16MC05X117MiwzMH0kXHJcbmBgYFxyXG5cclxuIyMjIENvbW1hbmQgdXNlZFxyXG5cclxuYGBgc2hlbGxcclxucHlsaW50XHJcbmBgYFxyXG5cclxuXHJcbiMjIyBQeWxpbnQgb3V0cHV0XHJcblxyXG5gYGBzaGVsbFxyXG4odmVudnRlc3QpIHRzdW5nLWhhbmRlLU1hY0Jvb2stUHJvOnJvYm90X2lzX2NvbW1pbmcgdHN1bmctaGFuJCBweWxpbnRcclxuVHJhY2ViYWNrIChtb3N0IHJlY2VudCBjYWxsIGxhc3QpOlxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2Jpbi9weWxpbnRcIiwgbGluZSA4LCBpbiA8bW9kdWxlPlxyXG4gICAgc3lzLmV4aXQocnVuX3B5bGludCgpKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvX19pbml0X18ucHlcIiwgbGluZSAyNSwgaW4gcnVuX3B5bGludFxyXG4gICAgUHlsaW50UnVuKGFyZ3Ygb3Igc3lzLmFyZ3ZbMTpdKVxyXG4gIEZpbGUgXCIvVXNlcnMvdHN1bmctaGFuL1B5Y2hhcm1Qcm9qZWN0cy9yb2JvdF9pc19jb21taW5nL3ZlbnZ0ZXN0L2xpYi9weXRob24zLjkvc2l0ZS1wYWNrYWdlcy9weWxpbnQvbGludC9ydW4ucHlcIiwgbGluZSAxNjEsIGluIF9faW5pdF9fXHJcbiAgICBhcmdzID0gX2NvbmZpZ19pbml0aWFsaXphdGlvbihcclxuICBGaWxlIFwiL1VzZXJzL3RzdW5nLWhhbi9QeWNoYXJtUHJvamVjdHMvcm9ib3RfaXNfY29tbWluZy92ZW52dGVzdC9saWIvcHl0aG9uMy45L3NpdGUtcGFja2FnZXMvcHlsaW50L2NvbmZpZy9jb25maWdfaW5pdGlhbGl6YXRpb24ucHlcIiwgbGluZSA1NywgaW4gX2NvbmZpZ19pbml0aWFsaXphdGlvblxyXG4gICAgbGludGVyLl9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGUoY29uZmlnX2FyZ3MpXHJcbiAgRmlsZSBcIi9Vc2Vycy90c3VuZy1oYW4vUHljaGFybVByb2plY3RzL3JvYm90X2lzX2NvbW1pbmcvdmVudnRlc3QvbGliL3B5dGhvbjMuOS9zaXRlLXBhY2thZ2VzL3B5bGludC9jb25maWcvYXJndW1lbnRzX21hbmFnZXIucHlcIiwgbGluZSAyNDQsIGluIF9wYXJzZV9jb25maWd1cmF0aW9uX2ZpbGVcclxuICAgIHNlbGYuY29uZmlnLCBwYXJzZWRfYXJncyA9IHNlbGYuX2FyZ19wYXJzZXIucGFyc2Vfa25vd25fYXJncyhcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxODU4LCBpbiBwYXJzZV9rbm93bl9hcmdzXHJcbiAgICBuYW1lc3BhY2UsIGFyZ3MgPSBzZWxmLl9wYXJzZV9rbm93bl9hcmdzKGFyZ3MsIG5hbWVzcGFjZSlcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAyMDY3LCBpbiBfcGFyc2Vfa25vd25fYXJnc1xyXG4gICAgc3RhcnRfaW5kZXggPSBjb25zdW1lX29wdGlvbmFsKHN0YXJ0X2luZGV4KVxyXG4gIEZpbGUgXCIvdXNyL2xvY2FsL0NlbGxhci9weXRob25AMy45LzMuOS4xM18xL0ZyYW1ld29ya3MvUHl0aG9uLmZyYW1ld29yay9WZXJzaW9ucy8zLjkvbGliL3B5dGhvbjMuOS9hcmdwYXJzZS5weVwiLCBsaW5lIDIwMDcsIGluIGNvbnN1bWVfb3B0aW9uYWxcclxuICAgIHRha2VfYWN0aW9uKGFjdGlvbiwgYXJncywgb3B0aW9uX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNfMS9GcmFtZXdvcmtzL1B5dGhvbi5mcmFtZXdvcmsvVmVyc2lvbnMvMy45L2xpYi9weXRob24zLjkvYXJncGFyc2UucHlcIiwgbGluZSAxOTE5LCBpbiB0YWtlX2FjdGlvblxyXG4gICAgYXJndW1lbnRfdmFsdWVzID0gc2VsZi5fZ2V0X3ZhbHVlcyhhY3Rpb24sIGFyZ3VtZW50X3N0cmluZ3MpXHJcbiAgRmlsZSBcIi91c3IvbG9jYWwvQ2VsbGFyL3B5dGhvbkAzLjkvMy45LjEzXzEvRnJhbWV3b3Jrcy9QeXRob24uZnJhbWV3b3JrL1ZlcnNpb25zLzMuOS9saWIvcHl0aG9uMy45L2FyZ3BhcnNlLnB5XCIsIGxpbmUgMjQ1MCwgaW4gX2dldF92YWx1ZXNcclxuICAgIHZhbHVlID0gc2VsZi5fZ2V0X3ZhbHVlKGFjdGlvbiwgYXJnX3N0cmluZylcclxuICBGaWxlIFwiL3Vzci9sb2NhbC9DZWxsYXIvcHl0aG9uQDMuOS8zLjkuMTNf
```
- `apu_characterization\out\oa01\runs\OA01-M-08-pylint-dev__pylint-7228\raw\env_snapshots.jsonl` lines≈13 size=14158
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-5875cd969af5428587e3de59a59607b4",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "exec_end_unix_ns": 1784227885582497675,
  "git_commit": "d597f252915ddcaaa15ccdfcb35670152cb83587\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:0f00ae73e3cc14ae45d4377b2f489211836be372a042bf4363ee8386ab96d158\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227886162548882,
  "snapshot_start_unix_ns": 1784227885635013049,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-0d2d8e56a0c948618da7e6757a3db9b6",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "exec_end_unix_ns": 1784227886084067973,
  "git_commit": "d597f252915ddcaaa15ccdfcb35670152cb83587\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:0f00ae73e3cc14ae45d4377b2f489211836be372a042bf4363ee8386ab96d158\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227886729271661,
  "snapshot_start_unix_ns": 1784227886241634151,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-12c888838877434b91c2b71adab8a1a2",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "exec_end_unix_ns": 1784227894423074982,
  "git_commit": "d597f252915ddcaaa15ccdfcb35670152cb83587\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:0f00ae73e3cc14ae45d4377b2f489211836be372a042bf4363ee8386ab96d158\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784227894798422315,
  "snapshot_start_unix_ns": 1784227894450726367,
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-08-pylint-dev__pylint-7228\raw\exec_events.jsonl` lines≈30 size=29813
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-defac22a",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-7228:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-aaae5f4e149d40eab01b7ba9f207bf92",
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228",
  "unix_ns": 1784227869555603061
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-defac22a",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pylint-dev_1776_pylint-7228:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-aaae5f4e149d40eab01b7ba9f207bf92",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-08-pylint-dev__pylint-7228/raw/tool_io/exec-aaae5f4e149d40eab01b7ba9f207bf92.stdout_stderr.bin",
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228",
  "unix_ns": 1784227869925584291
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
    "bash",
    "-c",
    "grep -r \"function-rgx\" ."
  ],
  "command": "bash\u0000-c\u0000grep -r \"function-rgx\" .",
  "container_id": "36b899bbc4eb7ac10aee89b272af5149796805cd8c51104d3fd9b29638ffdf32",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-5875cd969af5428587e3de59a59607b4",
  "trajectory_id": "OA01-M-08-pylint-dev__pylint-7228",
  "unix_ns": 1784227884466757577
}
```
- `apu_characterization\out\oa01\runs\OA01-M-09-scikit-learn__scikit-learn-13241\derived\exec_spans.jsonl` lines≈44 size=36812
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ce20a9a7",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.scikit-learn_1776_scikit-learn-13241:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 292.321206,
  "end_unix_ns": 1784228132709359273,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-72014a00f50e43b2839abfb3e2416b57",
  "start_unix_ns": 1784228132417038067,
  "timed_out": false,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
    "bash",
    "-c",
    "grep -rn 'class KernelPCA' ."
  ],
  "command": "bash\u0000-c\u0000grep -rn 'class KernelPCA' .",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "docker_operation": "exec",
  "duration_ms": 1254.983517,
  "end_unix_ns": 1784228149404565778,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-f447ffaa5d2746208563cc5cd4c1f569",
  "start_unix_ns": 1784228148149582261,
  "timed_out": false,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
    "bash",
    "-c",
    "ls -l /testbed"
  ],
  "command": "bash\u0000-c\u0000ls -l /testbed",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "docker_operation": "exec",
  "duration_ms": 205.210217,
  "end_unix_ns": 1784228149766581293,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-20f0f4d390cb4884b611a0741b1f9e09",
  "start_unix_ns": 1784228149561371076,
  "timed_out": false,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-09-scikit-learn__scikit-learn-13241\raw\api_boundary.jsonl` lines≈94 size=9138786
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-09-scikit-learn__scikit-learn-13241-call-0000-a4749c4c",
  "call_index": 0,
  "cost_usd": 0.005104,
  "derived_timing": {
    "upstream_body_ms": 0.457951,
    "upstream_first_byte_ms": 10510.497027,
    "upstream_total_ms": 10510.954978
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbkRpZmZlcmVuY2VzIGFtb25nIHRoZSByZXN1bHRzIG9mIEtlcm5lbFBDQSB3aXRoIHJiZiBrZXJuZWxcbkhpIHRoZXJlLFxyXG5JIG1ldCB3aXRoIGEgcHJvYmxlbTpcclxuXHJcbiMjIyMgRGVzY3JpcHRpb25cclxuV2hlbiBJIHJ1biBLZXJuZWxQQ0EgZm9yIGRpbWVuc2lvbiByZWR1Y3Rpb24gZm9yIHRoZSBzYW1lIGRhdGFzZXRzLCB0aGUgcmVzdWx0cyBhcmUgZGlmZmVyZW50IGluIHNpZ25zLlxyXG5cclxuIyMjIyBTdGVwcy9Db2RlIHRvIFJlcHJvZHVjZVxyXG5KdXN0IHRvIHJlZHVjZSB0aGUgZGltZW5zaW9uIHRvIDcgd2l0aCByYmYga2VybmVsOlxyXG5wY2EgPSBLZXJuZWxQQ0Eobl9jb21wb25lbnRzPTcsIGtlcm5lbD0ncmJmJywgY29weV9YPUZhbHNlLCBuX2pvYnM9LTEpXHJcbnBjYS5maXRfdHJhbnNmb3JtKFgpXHJcblxyXG4jIyMjIEV4cGVjdGVkIFJlc3VsdHNcclxuVGhlIHNhbWUgcmVzdWx0LlxyXG5cclxuIyMjIyBBY3R1YWwgUmVzdWx0c1xyXG5UaGUgcmVzdWx0cyBhcmUgdGhlIHNhbWUgZXhjZXB0IGZvciB0aGVpciBzaWduczooXHJcbltbLTAuNDQ0NTc2MTcgLTAuMTgxNTU4ODYgLTAuMTA4NzM0NzQgIDAuMTM1NDgzODYgLTAuMTQzNzE3NCAgLTAuMDU3NDY5XHQwLjE4MTI0MzY0XV0gXHJcblxyXG5bWyAwLjQ0NDU3NjE3ICAwLjE4MTU1ODg2ICAwLjEwODczNDc0IC0wLjEzNTQ4Mzg2IC0wLjE0MzcxNzQgIC0wLjA1NzQ2OSAtMC4xODEyNDM2NF1dIFxyXG5cclxuW1stMC40NDQ1NzYxNyAtMC4xODE1NTg4NiAgMC4xMDg3MzQ3NCAgMC4xMzU0ODM4NiAgMC4xNDM3MTc0ICAgMC4wNTc0NjkgIDAuMTgxMjQzNjRdXSBcclxuXHJcbiMjIyMgVmVyc2lvbnNcclxuMC4xOC4xXHJcblxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21tYW5kKHMpXG5cbkVhY2ggcmVzcG9uc2Ugc2hvdWxkIGluY2x1ZGU6XG5cbjEuICoqUmVhc29uaW5nIHRleHQqKiB3aGVyZSB5b3UgZXhwbGFpbiB5b3VyIGFuYWx5c2lzIGFuZCBwbGFuXG4yL
```

### sample[1]
```json
{
  "call_id": "OA01-M-09-scikit-learn__scikit-learn-13241-call-0001-fd89c7e7",
  "call_index": 1,
  "cost_usd": 0.00236,
  "derived_timing": {
    "upstream_body_ms": 0.134408,
    "upstream_first_byte_ms": 971.010891,
    "upstream_total_ms": 971.145299
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbkRpZmZlcmVuY2VzIGFtb25nIHRoZSByZXN1bHRzIG9mIEtlcm5lbFBDQSB3aXRoIHJiZiBrZXJuZWxcbkhpIHRoZXJlLFxyXG5JIG1ldCB3aXRoIGEgcHJvYmxlbTpcclxuXHJcbiMjIyMgRGVzY3JpcHRpb25cclxuV2hlbiBJIHJ1biBLZXJuZWxQQ0EgZm9yIGRpbWVuc2lvbiByZWR1Y3Rpb24gZm9yIHRoZSBzYW1lIGRhdGFzZXRzLCB0aGUgcmVzdWx0cyBhcmUgZGlmZmVyZW50IGluIHNpZ25zLlxyXG5cclxuIyMjIyBTdGVwcy9Db2RlIHRvIFJlcHJvZHVjZVxyXG5KdXN0IHRvIHJlZHVjZSB0aGUgZGltZW5zaW9uIHRvIDcgd2l0aCByYmYga2VybmVsOlxyXG5wY2EgPSBLZXJuZWxQQ0Eobl9jb21wb25lbnRzPTcsIGtlcm5lbD0ncmJmJywgY29weV9YPUZhbHNlLCBuX2pvYnM9LTEpXHJcbnBjYS5maXRfdHJhbnNmb3JtKFgpXHJcblxyXG4jIyMjIEV4cGVjdGVkIFJlc3VsdHNcclxuVGhlIHNhbWUgcmVzdWx0LlxyXG5cclxuIyMjIyBBY3R1YWwgUmVzdWx0c1xyXG5UaGUgcmVzdWx0cyBhcmUgdGhlIHNhbWUgZXhjZXB0IGZvciB0aGVpciBzaWduczooXHJcbltbLTAuNDQ0NTc2MTcgLTAuMTgxNTU4ODYgLTAuMTA4NzM0NzQgIDAuMTM1NDgzODYgLTAuMTQzNzE3NCAgLTAuMDU3NDY5XHQwLjE4MTI0MzY0XV0gXHJcblxyXG5bWyAwLjQ0NDU3NjE3ICAwLjE4MTU1ODg2ICAwLjEwODczNDc0IC0wLjEzNTQ4Mzg2IC0wLjE0MzcxNzQgIC0wLjA1NzQ2OSAtMC4xODEyNDM2NF1dIFxyXG5cclxuW1stMC40NDQ1NzYxNyAtMC4xODE1NTg4NiAgMC4xMDg3MzQ3NCAgMC4xMzU0ODM4NiAgMC4xNDM3MTc0ICAgMC4wNTc0NjkgIDAuMTgxMjQzNjRdXSBcclxuXHJcbiMjIyMgVmVyc2lvbnNcclxuMC4xOC4xXHJcblxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21tYW5kKHMpXG5cbkVhY2ggcmVzcG9uc2Ugc2hvdWxkIGluY2x1ZGU6XG5cbjEuICoqUmVhc29uaW5nIHRleHQqKiB3aGVyZSB5b3UgZXhwbGFpbiB5b3VyIGFuYWx5c2lzIGFuZCBwbGFuXG4yLiBBdC
```

### sample[2]
```json
{
  "call_id": "OA01-M-09-scikit-learn__scikit-learn-13241-call-0002-5bccb22d",
  "call_index": 2,
  "cost_usd": 0.0019,
  "derived_timing": {
    "upstream_body_ms": 0.099813,
    "upstream_first_byte_ms": 2150.871315,
    "upstream_total_ms": 2150.971128
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbkRpZmZlcmVuY2VzIGFtb25nIHRoZSByZXN1bHRzIG9mIEtlcm5lbFBDQSB3aXRoIHJiZiBrZXJuZWxcbkhpIHRoZXJlLFxyXG5JIG1ldCB3aXRoIGEgcHJvYmxlbTpcclxuXHJcbiMjIyMgRGVzY3JpcHRpb25cclxuV2hlbiBJIHJ1biBLZXJuZWxQQ0EgZm9yIGRpbWVuc2lvbiByZWR1Y3Rpb24gZm9yIHRoZSBzYW1lIGRhdGFzZXRzLCB0aGUgcmVzdWx0cyBhcmUgZGlmZmVyZW50IGluIHNpZ25zLlxyXG5cclxuIyMjIyBTdGVwcy9Db2RlIHRvIFJlcHJvZHVjZVxyXG5KdXN0IHRvIHJlZHVjZSB0aGUgZGltZW5zaW9uIHRvIDcgd2l0aCByYmYga2VybmVsOlxyXG5wY2EgPSBLZXJuZWxQQ0Eobl9jb21wb25lbnRzPTcsIGtlcm5lbD0ncmJmJywgY29weV9YPUZhbHNlLCBuX2pvYnM9LTEpXHJcbnBjYS5maXRfdHJhbnNmb3JtKFgpXHJcblxyXG4jIyMjIEV4cGVjdGVkIFJlc3VsdHNcclxuVGhlIHNhbWUgcmVzdWx0LlxyXG5cclxuIyMjIyBBY3R1YWwgUmVzdWx0c1xyXG5UaGUgcmVzdWx0cyBhcmUgdGhlIHNhbWUgZXhjZXB0IGZvciB0aGVpciBzaWduczooXHJcbltbLTAuNDQ0NTc2MTcgLTAuMTgxNTU4ODYgLTAuMTA4NzM0NzQgIDAuMTM1NDgzODYgLTAuMTQzNzE3NCAgLTAuMDU3NDY5XHQwLjE4MTI0MzY0XV0gXHJcblxyXG5bWyAwLjQ0NDU3NjE3ICAwLjE4MTU1ODg2ICAwLjEwODczNDc0IC0wLjEzNTQ4Mzg2IC0wLjE0MzcxNzQgIC0wLjA1NzQ2OSAtMC4xODEyNDM2NF1dIFxyXG5cclxuW1stMC40NDQ1NzYxNyAtMC4xODE1NTg4NiAgMC4xMDg3MzQ3NCAgMC4xMzU0ODM4NiAgMC4xNDM3MTc0ICAgMC4wNTc0NjkgIDAuMTgxMjQzNjRdXSBcclxuXHJcbiMjIyMgVmVyc2lvbnNcclxuMC4xOC4xXHJcblxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgY29tbWFuZChzKS48L2ltcG9ydGFudD5cblxuRm9yIGVhY2ggcmVzcG9uc2U6XG5cbjEuIEluY2x1ZGUgYSBUSE9VR0hUIHNlY3Rpb24gZXhwbGFpbmluZyB5b3VyIHJlYXNvbmluZyBhbmQgd2hhdCB5b3UncmUgdHJ5aW5nIHRvIGFjY29tcGxpc2hcbjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgYmFzaCB0b29sIGNhbGxzIHRvIGV4ZWN1dGVcblxuIyMgSW1wb3J0YW50IEJvdW5kYXJpZXNcblxuLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3Rlc3RiZWQgKHRoaXMgaXMgdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGZvciBhbGwgeW91ciBzdWJzZXF1ZW50IGNvbW1hbmRzKVxuLSBETyBOT1QgTU9ESUZZOiBUZXN0cywgY29uZmlndXJhdGlvbiBmaWxlcyAocHlwcm9qZWN0LnRvbWwsIHNldHVwLmNmZywgZXRjLilcblxuIyMgUmVjb21tZW5kZWQgV29ya2Zsb3dcblxuMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlc1xuMi4gQ3JlYXRlIGEgc2NyaXB0IHRvIHJlcHJvZHVjZSB0aGUgaXNzdWVcbjMuIEVkaXQgdGhlIHNvdXJjZSBjb2RlIHRvIHJlc29sdmUgdGhlIGlzc3VlXG40LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2FpblxuNS4gVGVzdCBlZGdlIGNhc2VzIHRvIGVuc3VyZSB5b3VyIGZpeCBpcyByb2J1c3RcblxuIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXNcblxuWW91IGFyZSBvcGVyYXRpbmcgaW4gYW4gZW52aXJvbm1lbnQgd2hlcmVcblxuMS4gWW91IGlzc3VlIGF0IGxlYXN0IG9uZSBjb21tYW5kXG4yLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIHRoZSBjb21tYW5kKHMpIGluIGEgc3Vic2hlbGxcbjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKVxuNC4gWW91IHdyaXRlIHlvdXIgbmV4dCBjb21tYW5kKHMpXG5cbkVhY2ggcmVzcG9uc2Ugc2hvdWxkIGluY2x1ZGU6XG5cbjEuICoqUmVhc29uaW5nIHRleHQqKiB3aGVyZSB5b3UgZXhwbGFpbiB5b3VyIGFuYWx5c2lzIGFuZCBwbGFuXG4yLiBBd
```
- `apu_characterization\out\oa01\runs\OA01-M-09-scikit-learn__scikit-learn-13241\raw\env_snapshots.jsonl` lines≈42 size=59509
  schema:
  - `after_span_id`: str
  - `container_id`: str
  - `exec_end_unix_ns`: int
  - `git_commit`: str
  - `git_commit_returncode`: int
  - `git_commit_truncated`: bool
  - `git_diff`: str
  - `git_diff_returncode`: int
  - `git_diff_truncated`: bool
  - `git_status`: str
  - `git_status_returncode`: int
  - `git_status_truncated`: bool
  - `image_id`: str
  - `image_id_returncode`: int
  - `image_id_truncated`: bool
  - `observer_mode`: str
  - `schema_version`: str
  - `snapshot_end_unix_ns`: int
  - `snapshot_start_unix_ns`: int
  - `trajectory_id`: str
### sample[0]
```json
{
  "after_span_id": "exec-f447ffaa5d2746208563cc5cd4c1f569",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "exec_end_unix_ns": 1784228149404565778,
  "git_commit": "f8b108d0c6f2f82b2dc4e32a6793f9d9ac9cf2f4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:53e2d47e8bb5995d1dd2eadf1548d5ce8506fbe6814ea8f8a627eb899bfaba0c\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784228149814301201,
  "snapshot_start_unix_ns": 1784228149440892567,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```

### sample[1]
```json
{
  "after_span_id": "exec-20f0f4d390cb4884b611a0741b1f9e09",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "exec_end_unix_ns": 1784228149766581293,
  "git_commit": "f8b108d0c6f2f82b2dc4e32a6793f9d9ac9cf2f4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:53e2d47e8bb5995d1dd2eadf1548d5ce8506fbe6814ea8f8a627eb899bfaba0c\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784228150297200355,
  "snapshot_start_unix_ns": 1784228149888222723,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```

### sample[2]
```json
{
  "after_span_id": "exec-3ec667fbf19c408b8aae0f3d9a7e69d2",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "exec_end_unix_ns": 1784228151248706698,
  "git_commit": "f8b108d0c6f2f82b2dc4e32a6793f9d9ac9cf2f4\n",
  "git_commit_returncode": 0,
  "git_commit_truncated": false,
  "git_diff": "",
  "git_diff_returncode": 0,
  "git_diff_truncated": false,
  "git_status": "",
  "git_status_returncode": 0,
  "git_status_truncated": false,
  "image_id": "sha256:53e2d47e8bb5995d1dd2eadf1548d5ce8506fbe6814ea8f8a627eb899bfaba0c\n",
  "image_id_returncode": 0,
  "image_id_truncated": false,
  "observer_mode": "asynchronous_nonblocking_sidecar",
  "schema_version": "oa01_env_snapshot_v1",
  "snapshot_end_unix_ns": 1784228151637275398,
  "snapshot_start_unix_ns": 1784228151288289133,
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-09-scikit-learn__scikit-learn-13241\raw\exec_events.jsonl` lines≈88 size=70862
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `event`: str
  - `schema_version`: str
  - `span_id`: str
  - `trajectory_id`: str
  - `unix_ns`: int
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ce20a9a7",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.scikit-learn_1776_scikit-learn-13241:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-72014a00f50e43b2839abfb3e2416b57",
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241",
  "unix_ns": 1784228132417038067
}
```

### sample[1]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-ce20a9a7",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.scikit-learn_1776_scikit-learn-13241:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "end",
  "returncode": 0,
  "schema_version": "oa01_exec_event_v1",
  "signal": null,
  "span_id": "exec-72014a00f50e43b2839abfb3e2416b57",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-M-09-scikit-learn__scikit-learn-13241/raw/tool_io/exec-72014a00f50e43b2839abfb3e2416b57.stdout_stderr.bin",
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241",
  "unix_ns": 1784228132709359273
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
    "bash",
    "-c",
    "grep -rn 'class KernelPCA' ."
  ],
  "command": "bash\u0000-c\u0000grep -rn 'class KernelPCA' .",
  "container_id": "6f4684e955d615026e8a165459cd5905034482d609226cb3de66b149725e72e8",
  "docker_operation": "exec",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-f447ffaa5d2746208563cc5cd4c1f569",
  "trajectory_id": "OA01-M-09-scikit-learn__scikit-learn-13241",
  "unix_ns": 1784228148149582261
}
```
- `apu_characterization\out\oa01\runs\OA01-M-10-matplotlib__matplotlib-25433\derived\exec_spans.jsonl` lines≈51 size=44897
  schema:
  - `argv`: list[str] len=10
  - `command`: NoneType
  - `container_id`: NoneType
  - `docker_operation`: str
  - `duration_ms`: float
  - `end_unix_ns`: int
  - `flags`: list[empty] len=0
  - `returncode`: int
  - `schema_version`: str
  - `signal`: NoneType
  - `span_id`: str
  - `start_unix_ns`: int
  - `timed_out`: bool
  - `trajectory_id`: str
### sample[0]
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-86efbf59",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-25433:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "duration_ms": 366.576437,
  "end_unix_ns": 1784228841267069822,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-be539aa4c0f94476968d22dc4793ee9d",
  "start_unix_ns": 1784228840900493385,
  "timed_out": false,
  "trajectory_id": "OA01-M-10-matplotlib__matplotlib-25433"
}
```

### sample[1]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "d2fe141e0b4fb29145226a4a27f8e6a0a3877301db3c5a64f83f980d0de66c35",
    "bash",
    "-c",
    "ls -l /testbed"
  ],
  "command": "bash\u0000-c\u0000ls -l /testbed",
  "container_id": "d2fe141e0b4fb29145226a4a27f8e6a0a3877301db3c5a64f83f980d0de66c35",
  "docker_operation": "exec",
  "duration_ms": 298.166954,
  "end_unix_ns": 1784228848930672734,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-fba7892c37a048ef8a20d9ef8ac9c6ba",
  "start_unix_ns": 1784228848632505780,
  "timed_out": false,
  "trajectory_id": "OA01-M-10-matplotlib__matplotlib-25433"
}
```

### sample[2]
```json
{
  "argv": [
    "exec",
    "-w",
    "/testbed",
    "-e",
    "PAGER=cat",
    "-e",
    "MANPAGER=cat",
    "-e",
    "LESS=-R",
    "-e",
    "PIP_PROGRESS_BAR=off",
    "-e",
    "TQDM_DISABLE=1",
    "-e",
    "BASH_ENV=/root/.bashrc",
    "d2fe141e0b4fb29145226a4a27f8e6a0a3877301db3c5a64f83f980d0de66c35",
    "bash",
    "-c",
    "ls -l /testbed/src"
  ],
  "command": "bash\u0000-c\u0000ls -l /testbed/src",
  "container_id": "d2fe141e0b4fb29145226a4a27f8e6a0a3877301db3c5a64f83f980d0de66c35",
  "docker_operation": "exec",
  "duration_ms": 182.052287,
  "end_unix_ns": 1784228852305208002,
  "flags": [],
  "returncode": 0,
  "schema_version": "oa01_exec_span_v1",
  "signal": null,
  "span_id": "exec-96ba62d8202149eb9bd82288d520a89e",
  "start_unix_ns": 1784228852123155715,
  "timed_out": false,
  "trajectory_id": "OA01-M-10-matplotlib__matplotlib-25433"
}
```
- `apu_characterization\out\oa01\runs\OA01-M-10-matplotlib__matplotlib-25433\raw\api_boundary.jsonl` lines≈124 size=15401586
  schema:
  - `call_id`: str
  - `call_index`: int
  - `cost_usd`: float
  - `derived_timing`: dict
  - `derived_timing.upstream_body_ms`: float
  - `derived_timing.upstream_first_byte_ms`: float
  - `derived_timing.upstream_total_ms`: float
  - `flags`: list[empty] len=0
  - `method`: str
  - `model_id`: str
  - `path`: str
  - `request_body_b64`: str
  - `request_headers`: dict
  - `request_headers.Accept`: str
  - `request_headers.Accept-Encoding`: str
  - `request_headers.Authorization`: str
  - `request_headers.Connection`: str
  - `request_headers.Content-Length`: str
  - `request_headers.Content-Type`: str
  - `request_headers.Host`: str
  - `request_headers.User-Agent`: str
  - `request_headers.X-Stainless-Arch`: str
  - `request_headers.X-Stainless-Async`: str
  - `request_headers.X-Stainless-Lang`: str
  - `request_headers.X-Stainless-OS`: str
  - `request_headers.X-Stainless-Package-Version`: str
  - `request_headers.X-Stainless-Raw-Response`: str
  - `request_headers.X-Stainless-Runtime`: str
  - `request_headers.X-Stainless-Runtime-Version`: str
  - `request_headers.x-stainless-read-timeout`: str
  - `request_headers.x-stainless-retry-count`: str
  - `request_json`: dict
  - `request_json.messages`: list[dict] len=2
  - `request_json.messages[].content`: str
  - `request_json.messages[].role`: str
  - `request_json.model`: str
  - `request_json.parallel_tool_calls`: bool
  - `request_json.tools`: list[dict] len=1
  - `request_json.tools[].function`: dict
  - `request_json.tools[].function.description`: str
  - `request_json.tools[].function.name`: str
  - `request_json.tools[].function.parameters`: dict
  - `request_json.tools[].function.parameters.properties`: dict
  - `request_json.tools[].function.parameters.required`: list[str] len=1
  - `request_json.tools[].function.parameters.type`: str
  - `request_json.tools[].type`: str
  - `request_received_unix_ns`: int
  - `response_body_b64`: str
  - `response_first_body_byte_unix_ns`: int
  - `response_headers`: dict
  - `response_headers.Access-Control-Expose-Headers`: str
  - `response_headers.CF-Cache-Status`: str
  - `response_headers.CF-Ray`: str
  - `response_headers.Connection`: str
  - `response_headers.Content-Encoding`: str
  - `response_headers.Content-Type`: str
  - `response_headers.Date`: str
  - `response_headers.Server`: str
  - `response_headers.Strict-Transport-Security`: str
  - `response_headers.Transfer-Encoding`: str
### sample[0]
```json
{
  "call_id": "OA01-M-10-matplotlib__matplotlib-25433-call-0000-344a1cad",
  "call_index": 0,
  "cost_usd": 0.003086,
  "derived_timing": {
    "upstream_body_ms": 0.164875,
    "upstream_first_byte_ms": 3174.695842,
    "upstream_total_ms": 3174.860717
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiB1c2luZyBjbGYgYW5kIHB5cGxvdC5kcmF3IGluIHJhbmdlIHNsaWRlciBvbl9jaGFuZ2VkIGNhbGxiYWNrIGJsb2NrcyBpbnB1dCB0byB3aWRnZXRzXG4jIyMgQnVnIHN1bW1hcnlcblxuV2hlbiB1c2luZyBjbGVhciBmaWd1cmUsIGFkZGluZyBuZXcgd2lkZ2V0cyBhbmQgdGhlbiByZWRyYXdpbmcgdGhlIGN1cnJlbnQgZmlndXJlIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2Ugc2xpZGVyIHRoZSBpbnB1dHMgdG8gYWxsIHRoZSB3aWRnZXRzIGluIHRoZSBmaWd1cmUgYXJlIGJsb2NrZWQuIFdoZW4gZG9pbmcgdGhlIHNhbWUgaW4gdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLCBldmVyeXRoaW5nIHdvcmtzIGZpbmUuXG5cbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cblxuYGBgcHl0aG9uXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcHlwbG90XHJcbmltcG9ydCBtYXRwbG90bGliLndpZGdldHMgYXMgd2lkZ2V0c1xyXG5cclxuZGVmIG9uY2hhbmdlZCh2YWx1ZXMpOlxyXG4gICAgcHJpbnQoXCJvbiBjaGFuZ2VkXCIpXHJcbiAgICBwcmludCh2YWx1ZXMpXHJcbiAgICBweXBsb3QuY2xmKClcclxuICAgIGFkZEVsZW1lbnRzKClcclxuICAgIHB5cGxvdC5kcmF3KClcclxuXHJcbmRlZiBvbmNsaWNrKGUpOlxyXG4gICAgcHJpbnQoXCJvbiBjbGlja1wiKVxyXG4gICAgcHlwbG90LmNsZigpXHJcbiAgICBhZGRFbGVtZW50cygpXHJcbiAgICBweXBsb3QuZHJhdygpXHJcblxyXG5kZWYgYWRkRWxlbWVudHMoKTpcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC40NSwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIHNsaWRlclxyXG4gICAgc2xpZGVyID0gd2lkZ2V0cy5SYW5nZVNsaWRlcihheCwgXCJUZXN0XCIsIHZhbG1pbj0xLCB2YWxtYXg9MTAsIHZhbGluaXQ9KDEsIDEwKSlcclxuICAgIHNsaWRlci5vbl9jaGFuZ2VkKG9uY2hhbmdlZClcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC4zMCwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIGJ1dHRvblxyXG4gICAgYnV0dG9uID0gd2lkZ2V0cy5CdXR0b24oYXgsIFwiVGVzdFwiKVxyXG4gICAgYnV0dG9uLm9uX2NsaWNrZWQob25jbGljaylcclxuXHJcbmFkZEVsZW1lbnRzKClcclxuXHJcbnB5cGxvdC5zaG93KClcbmBgYFxuXG5cbiMjIyBBY3R1YWwgb3V0Y29tZVxuXG5UaGUgd2lkZ2V0cyBjYW4ndCByZWNlaXZlIGFueSBpbnB1dCBmcm9tIGEgbW91c2UgY2xpY2ssIHdoZW4gcmVkcmF3aW5nIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2UgU2xpZGVyLiBcclxuV2hlbiB1c2luZyBhIGJ1dHRvbiwgdGhlcmUgaXMgbm8gcHJvYmxlbS5cblxuIyMjIEV4cGVjdGVkIG91dGNvbWVcblxuVGhlIHJhbmdlIHNsaWRlciBjYWxsYmFjayBvbl9jaGFuZ2VkIGJlaGF2ZXMgdGhlIHNhbWUgYXMgdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLlxuXG4jIyMgQWRkaXRpb25hbCBpbmZvcm1hdGlvblxuXG5UaGUgcHJvYmxlbSBhbHNvIG9jY3VycmVkIG9uIE1hbmphcm8gd2l0aDpcclxuLSBQeXRob24gdmVyc2lvbjogMy4xMC45XHJcbi0gTWF0cGxvdGxpYiB2ZXJzaW9uOiAzLjYuMlxyXG4tIE1hdHBsb3RsaWIgYmFja2VuZDogUXRBZ2dcclxuLSBJbnN0YWxsYXRpb24gb2YgbWF0cGxvdGxpYiB2aWEgTGludXggcGFja2FnZSBtYW5hZ2VyXHJcblxuXG4jIyMgT3BlcmF0aW5nIHN5c3RlbVxuXG5XaW5kb3dzIDEwXG5cbiMjIyBNYXRwbG90bGliIFZlcnNpb25cblxuMy42LjJcblxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxuXG5Ua0FnZ1xuXG4jIyMgUHl0aG9uIHZlcnNpb25cblxuMy4xMS4wXG5cbiMjIyBKdXB5dGVyIHZlcnNpb25cblxuX05vIHJlc3BvbnNlX1xuXG4jIyMgSW5zdGFsbGF0aW9uXG5cbnBpcFxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N
```

### sample[1]
```json
{
  "call_id": "OA01-M-10-matplotlib__matplotlib-25433-call-0001-5a3f2eb8",
  "call_index": 1,
  "cost_usd": 0.002312,
  "derived_timing": {
    "upstream_body_ms": 0.104591,
    "upstream_first_byte_ms": 3003.490476,
    "upstream_total_ms": 3003.595067
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiB1c2luZyBjbGYgYW5kIHB5cGxvdC5kcmF3IGluIHJhbmdlIHNsaWRlciBvbl9jaGFuZ2VkIGNhbGxiYWNrIGJsb2NrcyBpbnB1dCB0byB3aWRnZXRzXG4jIyMgQnVnIHN1bW1hcnlcblxuV2hlbiB1c2luZyBjbGVhciBmaWd1cmUsIGFkZGluZyBuZXcgd2lkZ2V0cyBhbmQgdGhlbiByZWRyYXdpbmcgdGhlIGN1cnJlbnQgZmlndXJlIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2Ugc2xpZGVyIHRoZSBpbnB1dHMgdG8gYWxsIHRoZSB3aWRnZXRzIGluIHRoZSBmaWd1cmUgYXJlIGJsb2NrZWQuIFdoZW4gZG9pbmcgdGhlIHNhbWUgaW4gdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLCBldmVyeXRoaW5nIHdvcmtzIGZpbmUuXG5cbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cblxuYGBgcHl0aG9uXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcHlwbG90XHJcbmltcG9ydCBtYXRwbG90bGliLndpZGdldHMgYXMgd2lkZ2V0c1xyXG5cclxuZGVmIG9uY2hhbmdlZCh2YWx1ZXMpOlxyXG4gICAgcHJpbnQoXCJvbiBjaGFuZ2VkXCIpXHJcbiAgICBwcmludCh2YWx1ZXMpXHJcbiAgICBweXBsb3QuY2xmKClcclxuICAgIGFkZEVsZW1lbnRzKClcclxuICAgIHB5cGxvdC5kcmF3KClcclxuXHJcbmRlZiBvbmNsaWNrKGUpOlxyXG4gICAgcHJpbnQoXCJvbiBjbGlja1wiKVxyXG4gICAgcHlwbG90LmNsZigpXHJcbiAgICBhZGRFbGVtZW50cygpXHJcbiAgICBweXBsb3QuZHJhdygpXHJcblxyXG5kZWYgYWRkRWxlbWVudHMoKTpcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC40NSwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIHNsaWRlclxyXG4gICAgc2xpZGVyID0gd2lkZ2V0cy5SYW5nZVNsaWRlcihheCwgXCJUZXN0XCIsIHZhbG1pbj0xLCB2YWxtYXg9MTAsIHZhbGluaXQ9KDEsIDEwKSlcclxuICAgIHNsaWRlci5vbl9jaGFuZ2VkKG9uY2hhbmdlZClcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC4zMCwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIGJ1dHRvblxyXG4gICAgYnV0dG9uID0gd2lkZ2V0cy5CdXR0b24oYXgsIFwiVGVzdFwiKVxyXG4gICAgYnV0dG9uLm9uX2NsaWNrZWQob25jbGljaylcclxuXHJcbmFkZEVsZW1lbnRzKClcclxuXHJcbnB5cGxvdC5zaG93KClcbmBgYFxuXG5cbiMjIyBBY3R1YWwgb3V0Y29tZVxuXG5UaGUgd2lkZ2V0cyBjYW4ndCByZWNlaXZlIGFueSBpbnB1dCBmcm9tIGEgbW91c2UgY2xpY2ssIHdoZW4gcmVkcmF3aW5nIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2UgU2xpZGVyLiBcclxuV2hlbiB1c2luZyBhIGJ1dHRvbiwgdGhlcmUgaXMgbm8gcHJvYmxlbS5cblxuIyMjIEV4cGVjdGVkIG91dGNvbWVcblxuVGhlIHJhbmdlIHNsaWRlciBjYWxsYmFjayBvbl9jaGFuZ2VkIGJlaGF2ZXMgdGhlIHNhbWUgYXMgdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLlxuXG4jIyMgQWRkaXRpb25hbCBpbmZvcm1hdGlvblxuXG5UaGUgcHJvYmxlbSBhbHNvIG9jY3VycmVkIG9uIE1hbmphcm8gd2l0aDpcclxuLSBQeXRob24gdmVyc2lvbjogMy4xMC45XHJcbi0gTWF0cGxvdGxpYiB2ZXJzaW9uOiAzLjYuMlxyXG4tIE1hdHBsb3RsaWIgYmFja2VuZDogUXRBZ2dcclxuLSBJbnN0YWxsYXRpb24gb2YgbWF0cGxvdGxpYiB2aWEgTGludXggcGFja2FnZSBtYW5hZ2VyXHJcblxuXG4jIyMgT3BlcmF0aW5nIHN5c3RlbVxuXG5XaW5kb3dzIDEwXG5cbiMjIyBNYXRwbG90bGliIFZlcnNpb25cblxuMy42LjJcblxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxuXG5Ua0FnZ1xuXG4jIyMgUHl0aG9uIHZlcnNpb25cblxuMy4xMS4wXG5cbiMjIyBKdXB5dGVyIHZlcnNpb25cblxuX05vIHJlc3BvbnNlX1xuXG4jIyMgSW5zdGFsbGF0aW9uXG5cbnBpcFxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N
```

### sample[2]
```json
{
  "call_id": "OA01-M-10-matplotlib__matplotlib-25433-call-0002-ded52d82",
  "call_index": 2,
  "cost_usd": 0.002946,
  "derived_timing": {
    "upstream_body_ms": 0.073466,
    "upstream_first_byte_ms": 3659.876595,
    "upstream_total_ms": 3659.950061
  },
  "flags": [],
  "method": "POST",
  "model_id": "gpt-4.1",
  "path": "/v1/chat/completions",
  "request_body_b64": "eyJtZXNzYWdlcyI6W3sicm9sZSI6InN5c3RlbSIsImNvbnRlbnQiOiJZb3UgYXJlIGEgaGVscGZ1bCBhc3Npc3RhbnQgdGhhdCBjYW4gaW50ZXJhY3Qgd2l0aCBhIGNvbXB1dGVyIHNoZWxsIHRvIHNvbHZlIHByb2dyYW1taW5nIHRhc2tzLiJ9LHsicm9sZSI6InVzZXIiLCJjb250ZW50IjoiPHByX2Rlc2NyaXB0aW9uPlxuQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjpcbltCdWddOiB1c2luZyBjbGYgYW5kIHB5cGxvdC5kcmF3IGluIHJhbmdlIHNsaWRlciBvbl9jaGFuZ2VkIGNhbGxiYWNrIGJsb2NrcyBpbnB1dCB0byB3aWRnZXRzXG4jIyMgQnVnIHN1bW1hcnlcblxuV2hlbiB1c2luZyBjbGVhciBmaWd1cmUsIGFkZGluZyBuZXcgd2lkZ2V0cyBhbmQgdGhlbiByZWRyYXdpbmcgdGhlIGN1cnJlbnQgZmlndXJlIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2Ugc2xpZGVyIHRoZSBpbnB1dHMgdG8gYWxsIHRoZSB3aWRnZXRzIGluIHRoZSBmaWd1cmUgYXJlIGJsb2NrZWQuIFdoZW4gZG9pbmcgdGhlIHNhbWUgaW4gdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLCBldmVyeXRoaW5nIHdvcmtzIGZpbmUuXG5cbiMjIyBDb2RlIGZvciByZXByb2R1Y3Rpb25cblxuYGBgcHl0aG9uXG5pbXBvcnQgbWF0cGxvdGxpYi5weXBsb3QgYXMgcHlwbG90XHJcbmltcG9ydCBtYXRwbG90bGliLndpZGdldHMgYXMgd2lkZ2V0c1xyXG5cclxuZGVmIG9uY2hhbmdlZCh2YWx1ZXMpOlxyXG4gICAgcHJpbnQoXCJvbiBjaGFuZ2VkXCIpXHJcbiAgICBwcmludCh2YWx1ZXMpXHJcbiAgICBweXBsb3QuY2xmKClcclxuICAgIGFkZEVsZW1lbnRzKClcclxuICAgIHB5cGxvdC5kcmF3KClcclxuXHJcbmRlZiBvbmNsaWNrKGUpOlxyXG4gICAgcHJpbnQoXCJvbiBjbGlja1wiKVxyXG4gICAgcHlwbG90LmNsZigpXHJcbiAgICBhZGRFbGVtZW50cygpXHJcbiAgICBweXBsb3QuZHJhdygpXHJcblxyXG5kZWYgYWRkRWxlbWVudHMoKTpcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC40NSwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIHNsaWRlclxyXG4gICAgc2xpZGVyID0gd2lkZ2V0cy5SYW5nZVNsaWRlcihheCwgXCJUZXN0XCIsIHZhbG1pbj0xLCB2YWxtYXg9MTAsIHZhbGluaXQ9KDEsIDEwKSlcclxuICAgIHNsaWRlci5vbl9jaGFuZ2VkKG9uY2hhbmdlZClcclxuICAgIGF4ID0gcHlwbG90LmF4ZXMoWzAuMSwgMC4zMCwgMC44LCAwLjFdKVxyXG4gICAgZ2xvYmFsIGJ1dHRvblxyXG4gICAgYnV0dG9uID0gd2lkZ2V0cy5CdXR0b24oYXgsIFwiVGVzdFwiKVxyXG4gICAgYnV0dG9uLm9uX2NsaWNrZWQob25jbGljaylcclxuXHJcbmFkZEVsZW1lbnRzKClcclxuXHJcbnB5cGxvdC5zaG93KClcbmBgYFxuXG5cbiMjIyBBY3R1YWwgb3V0Y29tZVxuXG5UaGUgd2lkZ2V0cyBjYW4ndCByZWNlaXZlIGFueSBpbnB1dCBmcm9tIGEgbW91c2UgY2xpY2ssIHdoZW4gcmVkcmF3aW5nIGluIHRoZSBvbl9jaGFuZ2VkIGNhbGxiYWNrIG9mIGEgcmFuZ2UgU2xpZGVyLiBcclxuV2hlbiB1c2luZyBhIGJ1dHRvbiwgdGhlcmUgaXMgbm8gcHJvYmxlbS5cblxuIyMjIEV4cGVjdGVkIG91dGNvbWVcblxuVGhlIHJhbmdlIHNsaWRlciBjYWxsYmFjayBvbl9jaGFuZ2VkIGJlaGF2ZXMgdGhlIHNhbWUgYXMgdGhlIGJ1dHRvbiBjYWxsYmFjayBvbl9jbGlja2VkLlxuXG4jIyMgQWRkaXRpb25hbCBpbmZvcm1hdGlvblxuXG5UaGUgcHJvYmxlbSBhbHNvIG9jY3VycmVkIG9uIE1hbmphcm8gd2l0aDpcclxuLSBQeXRob24gdmVyc2lvbjogMy4xMC45XHJcbi0gTWF0cGxvdGxpYiB2ZXJzaW9uOiAzLjYuMlxyXG4tIE1hdHBsb3RsaWIgYmFja2VuZDogUXRBZ2dcclxuLSBJbnN0YWxsYXRpb24gb2YgbWF0cGxvdGxpYiB2aWEgTGludXggcGFja2FnZSBtYW5hZ2VyXHJcblxuXG4jIyMgT3BlcmF0aW5nIHN5c3RlbVxuXG5XaW5kb3dzIDEwXG5cbiMjIyBNYXRwbG90bGliIFZlcnNpb25cblxuMy42LjJcblxuIyMjIE1hdHBsb3RsaWIgQmFja2VuZFxuXG5Ua0FnZ1xuXG4jIyMgUHl0aG9uIHZlcnNpb25cblxuMy4xMS4wXG5cbiMjIyBKdXB5dGVyIHZlcnNpb25cblxuX05vIHJlc3BvbnNlX1xuXG4jIyMgSW5zdGFsbGF0aW9uXG5cbnBpcFxuXG48L3ByX2Rlc2NyaXB0aW9uPlxuXG48aW5zdHJ1Y3Rpb25zPlxuIyBUYXNrIEluc3RydWN0aW9uc1xuXG4jIyBPdmVydmlld1xuXG5Zb3UncmUgYSBzb2Z0d2FyZSBlbmdpbmVlciBpbnRlcmFjdGluZyBjb250aW51b3VzbHkgd2l0aCBhIGNvbXB1dGVyIGJ5IHN1Ym1pdHRpbmcgY29tbWFuZHMuXG5Zb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLlxuWW91ciB0YXNrIGlzIHNwZWNpZmljYWxseSB0byBtYWtlIGNoYW5nZXMgdG8gbm9uLXRlc3QgZmlsZXMgaW4gdGhlIGN1cnJlbnQgZGlyZWN0b3J5IGluIG9yZGVyIHRvIGZpeCB0aGUgaXNzdWUgZGVzY3JpYmVkIGluIHRoZSBQUiBkZXNjcmlwdGlvbiBpbiBhIHdheSB0aGF0IGlzIGdlbmVyYWwgYW5kIGNvbnNpc3RlbnQgd2l0aCB0aGUgY29kZWJhc2UuXG48SU1QT1JUQU5UPlRoaXMgaXMgYW4gaW50ZXJhY3RpdmUgcHJvY2VzcyB3aGVyZSB5b3Ugd2lsbCB0aGluayBhbmQgaXNzdWUgQVQgTEVBU1QgT05FIGNvbW1hbmQsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N
```


## 3. CAP-01

Exists: True
Candidate files (filtered): 35

### `apu_characterization\out\cap01\classification.json` size=163512
- format: JSON
- top keys: ['classification_manifest_sha256', 'note', 'oracle_spot_verify', 'shuffles', 'tasks']
- schema:
  - `classification_manifest_sha256`: str
  - `note`: str
  - `oracle_spot_verify`: dict
  - `oracle_spot_verify.CODE`: dict
  - `oracle_spot_verify.CODE.checked`: int
  - `oracle_spot_verify.CODE.oracle_verifier_mismatches`: int
  - `oracle_spot_verify.CODE.task_id`: str
  - `oracle_spot_verify.FUNCTION_CALLING`: dict
  - `oracle_spot_verify.FUNCTION_CALLING.checked`: int
  - `oracle_spot_verify.FUNCTION_CALLING.oracle_verifier_mismatches`: int
  - `oracle_spot_verify.FUNCTION_CALLING.task_id`: str
  - `oracle_spot_verify.MATH`: dict
  - `oracle_spot_verify.MATH.checked`: int
  - `oracle_spot_verify.MATH.oracle_verifier_mismatches`: int
  - `oracle_spot_verify.MATH.task_id`: str
  - `oracle_spot_verify.STRUCTURED_EXTRACTION`: dict
  - `oracle_spot_verify.STRUCTURED_EXTRACTION.checked`: int
  - `oracle_spot_verify.STRUCTURED_EXTRACTION.oracle_verifier_mismatches`: int
  - `oracle_spot_verify.STRUCTURED_EXTRACTION.task_id`: str
  - `oracle_spot_verify.TEXT_TO_SQL`: dict
  - `oracle_spot_verify.TEXT_TO_SQL.checked`: int
  - `oracle_spot_verify.TEXT_TO_SQL.oracle_verifier_mismatches`: int
  - `oracle_spot_verify.TEXT_TO_SQL.task_id`: str
  - `oracle_spot_verify.pass`: bool
  - `oracle_spot_verify.total_checked`: int
  - `oracle_spot_verify.total_mismatches`: int
  - `shuffles`: int
  - `tasks`: list[dict] len=250
  - `tasks[].classification`: str
  - `tasks[].correctness_sha256`: str
  - `tasks[].dead_n`: int
  - `tasks[].digest`: str
  - `tasks[].legacy_dead_at_128`: bool
  - `tasks[].legacy_dead_n`: int
  - `tasks[].pool_sha256`: str
  - `tasks[].saturated_n`: int
  - `tasks[].secondary_labels`: list[empty] len=0
  - `tasks[].shuffles`: int
  - `tasks[].solved_probability_n128`: float
  - `tasks[].solved_probability_n2048`: float
  - `tasks[].solved_probability_n4`: float
  - `tasks[].task_class`: str
  - `tasks[].task_id`: str
```json
{
  "classification_manifest_sha256": "f45732e33a352ed8c2fae5012d14263ed980f201f2997bb584930aa2cbe42055",
  "note": "Correctness for synthetic_debug pools uses the generator oracle after a per-domain verifier spot-check (32 candidates). Replace with full offline verify_candidate sweep when OpenAI pools land.",
  "oracle_spot_verify": {
    "CODE": {
      "checked": 32,
      "oracle_verifier_mismatches": 0,
      "task_id": "CODE-001"
    },
    "FUNCTION_CALLING": {
      "checked": 32,
      "oracle_verifier_mismatches": 0,
      "task_id": "FC-001"
    },
    "MATH": {
      "checked": 32,
      "oracle_verifier_mismatches": 0,
      "task_id": "MATH-001"
    },
    "STRUCTURED_EXTRACTION": {
      "checked": 32,
      "oracle_verifier_mismatches": 0,
      "task_id": "EXT-001"
    },
    "TEXT_TO_SQL": {
      "checked": 32,
      "oracle_verifier_mismatches": 0,
      "task_id": "SQL-001"
    },
    "pass": true,
    "total_checked": 160,
    "total_mismatches": 0
  },
  "shuffles": 50,
  "tasks": [
    {
      "classification": "SCALING",
      "correctness_sha256": "5894b0d5db7155e66bc9366a024931854798ef8bb61be7969954906cf165f91b",
      "dead_n": 2048,
      "digest": "30ba8404a1635a01568d2dad58b29f1be45067a7f9fbc2e32150e903f6b3b979",
      "legacy_dead_at_128": false,
      "legacy_dead_n": 128,
      "pool_sha256": "3f2434e1055f2249203acdacb912090c6b631e2bcaf6fa57200296295c336b97",
      "saturated_n": 4,
      "secondary_labels": [],
      "shuffles": 50,
      "solved_probability_n128": 1.0,
      "solved_probability_n2048": 1.0,
      "solved_probability_n4": 0.5,
      "task_class": "SCALING",
      "task_id": "CODE-001"
    },
    {
      "classification": "SCALING",
      "correctness_sha256": "d048442817211f27cb7dfcebae91efdf1cd4648edd50e4e91e43391e1620ebdf",
      "dead_n": 2048,
      "digest": "e92da9041f0a5a9895c49c29e5158f925dbd4678d5bd52c752a8ab5dba429d59",
      "legacy_dead_at_128": false,
      "legacy_dead_n": 128,
      "pool_sha256": "94a8db4da4ef84515078db8284eb6d6b0f753fd40cd780b88843d85241b297eb",
      "saturated_n": 4,
      "secondary_labels": [],
      "shuffles": 50,
      "solved_probability_n128": 1.0,
      "solved_probability_n2048": 1.0,
      "solved_probability_n4": 0.54,
      "task_class": "SCALING",
      "task_id": "CODE-002"
    },
    {
      "classification": "SCALING",
      "correctness_sha256": "89be3c770218ab45506b386e5fef7e586cd6e47993859e5d8bf35271b99a9798",
      "dead_n": 2048,
      "digest": "e5
```

### `apu_characterization\out\cap01\corpus.json` size=1044422
- format: JSON
- top keys: ['answer_space_sha256', 'corpus_kind', 'corpus_sha256', 'domain_counts', 'experiment', 'scope_exclusions', 'source_roots', 'task_count', 'tasks']
- schema:
  - `answer_space_sha256`: str
  - `corpus_kind`: str
  - `corpus_sha256`: str
  - `domain_counts`: dict
  - `domain_counts.CODE`: int
  - `domain_counts.FUNCTION_CALLING`: int
  - `domain_counts.MATH`: int
  - `domain_counts.STRUCTURED_EXTRACTION`: int
  - `domain_counts.TEXT_TO_SQL`: int
  - `experiment`: str
  - `scope_exclusions`: dict
  - `scope_exclusions.CODE`: str
  - `scope_exclusions.FUNCTION_CALLING`: str
  - `scope_exclusions.MATH`: str
  - `scope_exclusions.STRUCTURED_EXTRACTION`: str
  - `scope_exclusions.TEXT_TO_SQL`: str
  - `source_roots`: dict
  - `source_roots.bfcl`: str
  - `source_roots.bird`: str
  - `source_roots.cord`: str
  - `source_roots.humaneval`: str
  - `source_roots.math`: str
  - `task_count`: int
  - `tasks`: list[dict] len=250
  - `tasks[].contamination_note`: str
  - `tasks[].domain`: str
  - `tasks[].license`: str
  - `tasks[].prompt`: str
  - `tasks[].provenance`: str
  - `tasks[].source`: str
  - `tasks[].source_version`: str
  - `tasks[].task_id`: str
  - `tasks[].task_sha256`: str
  - `tasks[].verifier`: dict
  - `tasks[].verifier.entry_point`: str
  - `tasks[].verifier.source_task_id`: str
  - `tasks[].verifier.tests_path`: str
  - `tasks[].verifier.tests_sha256`: str
```json
{
  "answer_space_sha256": "8443e85d40fdf9a5f845de933991254dea60b1af9f314ea24555a9d35b4b4060",
  "corpus_kind": "licensed_live_sources",
  "corpus_sha256": "fbe50ea917cf1f1b1e33b0021a5bb45e261d421eeb4ea0a1025bc5cb5fcf86ba",
  "domain_counts": {
    "CODE": 50,
    "FUNCTION_CALLING": 50,
    "MATH": 50,
    "STRUCTURED_EXTRACTION": 50,
    "TEXT_TO_SQL": 50
  },
  "experiment": "CAP-01",
  "scope_exclusions": {
    "CODE": "HumanEval+/MBPP-style hidden-test tasks only; no live shell.",
    "FUNCTION_CALLING": "BFCL Multi-Turn subset excluded from CAP-01; single-turn and parallel-turn only (died-ledger #4).",
    "MATH": "Exact-answer / numeric-tolerance MATH only.",
    "STRUCTURED_EXTRACTION": "Fixed-document extraction with frozen normalization; double-keyed truth.",
    "TEXT_TO_SQL": "BIRD interactive mode excluded from CAP-01; static verifier only (died-ledger #3)."
  },
  "source_roots": {
    "bfcl": "bfcl-wheel/unpacked",
    "bird": "bird-minidev.zip",
    "cord": "cord-v2-hf + cord-v2-test.parquet",
    "humaneval": "humanevalplus-hf/test.jsonl",
    "math": "competition-math-hf/data"
  },
  "task_count": 250,
  "tasks": [
    {
      "contamination_note": "HumanEval+/MBPP-style hidden-test tasks only; no live shell. HumanEval+ public test split; extended hidden tests pinned. Memorization risk disclosed for public coding benchmarks.",
      "domain": "CODE",
      "license": "Apache-2.0",
      "prompt": "from typing import List\n\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    \"\"\" Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    \"\"\"\n",
      "provenance": "evalplus/humanevalplus task_id=HumanEval/0",
      "source": "HumanEval+",
      "source_version": "v0.1.10",
      "task_id": "CODE-001",
      "task_sha256": "083f7078f12dcdf7c67400256664675c95e34dda063d65250c11c900a3d0cf36",
      "verifier": {
        "entry_point": "has_close_elements",
        "source_task_id": "HumanEval/0",
        "tests_path": "apu_characterization/out/cap01/corpus_root/assets/code/CODE-001_tests.py",
        "tests_sha256": "cc10fcacca69b93bf3852b37af2d806997c7e6c5a6409302bd1be07117e9197a"
      }
    },
    {
      "contamination_note": "HumanEval+/MBPP-style hidden-test tasks only; no live shell. HumanEval+ public test split; extended
```

### `apu_characterization\out\cap01\excluded_tasks.json` size=794
- format: JSON
- top keys: ['protocol', 'died_ledger_ids', 'excluded_from_pools', 'pool_eligible_counts_after_exclusion']
- schema:
  - `died_ledger_ids`: list[int] len=1
  - `excluded_from_pools`: dict
  - `excluded_from_pools.EXT-017`: str
  - `excluded_from_pools.EXT-027`: str
  - `excluded_from_pools.EXT-030`: str
  - `excluded_from_pools.EXT-032`: str
  - `excluded_from_pools.EXT-034`: str
  - `excluded_from_pools.MATH-019`: str
  - `excluded_from_pools.SQL-041`: str
  - `pool_eligible_counts_after_exclusion`: dict
  - `pool_eligible_counts_after_exclusion.CODE`: int
  - `pool_eligible_counts_after_exclusion.FUNCTION_CALLING`: int
  - `pool_eligible_counts_after_exclusion.MATH`: int
  - `pool_eligible_counts_after_exclusion.STRUCTURED_EXTRACTION`: int
  - `pool_eligible_counts_after_exclusion.TEXT_TO_SQL`: int
  - `protocol`: str
```json
{
  "protocol": "cap01_v2.2",
  "died_ledger_ids": [
    13
  ],
  "excluded_from_pools": {
    "MATH-019": "truncated boxed answer in corpus extract",
    "SQL-041": "gold SQL OperationalError interrupted (sqlite timeout)",
    "EXT-017": "inferred schema requires menu[].sub but gold omits it",
    "EXT-027": "inferred schema requires menu[].price but gold omits it",
    "EXT-030": "inferred schema forbids menu[].sub but gold includes it",
    "EXT-032": "inferred schema forbids menu[].discountprice but gold includes it",
    "EXT-034": "inferred schema forbids menu[].discountprice but gold includes it"
  },
  "pool_eligible_counts_after_exclusion": {
    "FUNCTION_CALLING": 50,
    "TEXT_TO_SQL": 49,
    "CODE": 50,
    "MATH": 49,
    "STRUCTURED_EXTRACTION": 45
  }
}
```

### `apu_characterization\out\cap01\ext_near_miss_audit.json` size=19119
- format: JSON
- top keys: ['criterion', 'sample', 'options', 'recommendation', 'recommendation_rationale']
- schema:
  - `criterion`: str
  - `options`: dict
  - `options.a_keep_exact_match`: str
  - `options.b_field_level_f1`: str
  - `recommendation`: str
  - `recommendation_rationale`: str
  - `sample`: list[dict] len=5
  - `sample[].any_exact_pass`: bool
  - `sample[].candidates_scored`: int
  - `sample[].gold_exact_match_ok`: bool
  - `sample[].jsonish_count`: int
  - `sample[].menu_mention_count`: int
  - `sample[].samples`: list[dict] len=4
  - `sample[].samples[].content_preview`: str
  - `sample[].samples[].error`: str
  - `sample[].samples[].looks_json_object`: bool
  - `sample[].samples[].mentions_menu`: bool
  - `sample[].samples[].ordinal`: int
  - `sample[].samples[].solved`: bool
  - `sample[].samples[].status`: str
  - `sample[].task_id`: str
```json
{
  "criterion": "exact normalized gt_parse match after schema validate",
  "sample": [
    {
      "task_id": "EXT-001",
      "gold_exact_match_ok": true,
      "candidates_scored": 4,
      "any_exact_pass": false,
      "jsonish_count": 4,
      "menu_mention_count": 2,
      "samples": [
        {
          "ordinal": 0,
          "solved": false,
          "status": "wrong",
          "error": "ValidationError: Additional properties are not allowed ('subtotal' was unexpected)\n\nFailed validating 'additionalProperties' in schema:\n    {'$schema': 'https://json-schema.org/draft/2020-12/schema',\n     'additionalProperties': False,\n    ",
          "looks_json_object": true,
          "mentions_menu": true,
          "content_preview": "{\n  \"menu\": {\n    \"num\": \"901016\",\n    \"name\": \"-TICKET CP\",\n    \"count\": 2,\n    \"price\": 60.0,\n    \"item_subtotal\": 60.0\n  },\n  \"subtotal\": {\n    \"discount_price\": -60.0,\n    \"tax_price\": 5.455,\n    \"subtotal_price\": 60.0\n  },\n  \"total\": {\n    \"total_price\": 60.0,\n    \"menu_quantity_count\": 2,\n    \"credit_card_price\": 60.0,\n    \"credit_card_info\": \"EDC CIMB NIAGA No: xx7730\"\n  }\n}"
        },
        {
          "ordinal": 1,
          "solved": false,
          "status": "wrong",
          "error": "ValidationError: Additional properties are not allowed ('count', 'item_subtotal', 'name', 'number' were unexpected)\n\nFailed validating 'additionalProperties' in schema['properties']['menu']:\n    {'additionalProperties': False,\n     'propert",
          "looks_json_object": true,
          "mentions_menu": true,
          "content_preview": "{\n  \"menu\": {\n    \"number\": \"901016\",\n    \"name\": \"-TICKET CP\",\n    \"count\": 2,\n    \"price\": 60.000,\n    \"item_subtotal\": 60.000\n  },\n  \"sub_total\": {\n    \"discount_price\": -60.000,\n    \"tax_price\": 5.455,\n    \"subtotal_price\": 60.000\n  },\n  \"total\": {\n    \"total_price\": 60.000,\n    \"menu_quantity_count\": 2,\n    \"credit_card_price\": {\n      \"method\": \"EDC CIMB NIAGA\",\n      \"last_four_digits\": \"77"
        },
        {
          "ordinal": 2,
          "solved": false,
          "status": "wrong",
          "error": "ValidationError: Additional properties are not allowed ('receipt' was unexpected)\n\nFailed validating 'additionalProperties' in schema:\n    {'$schema': 'https://json-schema.org/draft/2020-12/schema',\n     'additionalProperties': False,\n     ",
          "
```

### `apu_characterization\out\cap01\frontier_probe_sql_ext.json` size=4472
- format: JSON
- top keys: ['model', 'n_candidates', 'interpretation_table_preregistered', 'elapsed_s', 'summary', 'rows', 'note', 'post_sql_alias_fix_rescore']
- schema:
  - `elapsed_s`: float
  - `interpretation_table_preregistered`: dict
  - `interpretation_table_preregistered.frontier_near_zero_and_mini_near_zero`: str
  - `interpretation_table_preregistered.frontier_scores_well_and_mini_near_zero`: str
  - `model`: str
  - `n_candidates`: int
  - `note`: str
  - `post_sql_alias_fix_rescore`: dict
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL`: dict
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task`: dict
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task.SQL-001`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task.SQL-010`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task.SQL-020`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task.SQL-030`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.by_task.SQL-040`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.mean_phat`: float
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.total_candidates`: int
  - `post_sql_alias_fix_rescore.TEXT_TO_SQL.total_correct`: int
  - `post_sql_alias_fix_rescore.interpretation`: str
  - `post_sql_alias_fix_rescore.note`: str
  - `rows`: list[dict] len=10
  - `rows[].domain`: str
  - `rows[].model`: str
  - `rows[].n`: int
  - `rows[].n_correct`: int
  - `rows[].phat`: float
  - `rows[].prompt_has_schema`: bool
  - `rows[].rendered_prompt_sha16`: str
  - `rows[].status_counts`: dict
  - `rows[].status_counts.wrong`: int
  - `rows[].task_id`: str
  - `summary`: dict
  - `summary.STRUCTURED_EXTRACTION`: dict
  - `summary.STRUCTURED_EXTRACTION.any_solve`: bool
  - `summary.STRUCTURED_EXTRACTION.mean_phat`: float
  - `summary.STRUCTURED_EXTRACTION.tasks`: int
  - `summary.STRUCTURED_EXTRACTION.total_candidates`: int
  - `summary.STRUCTURED_EXTRACTION.total_correct`: int
  - `summary.TEXT_TO_SQL`: dict
  - `summary.TEXT_TO_SQL.any_solve`: bool
  - `summary.TEXT_TO_SQL.mean_phat`: float
  - `summary.TEXT_TO_SQL.tasks`: int
  - `summary.TEXT_TO_SQL.total_candidates`: int
  - `summary.TEXT_TO_SQL.total_correct`: int
```json
{
  "model": "gpt-4o",
  "n_candidates": 4,
  "interpretation_table_preregistered": {
    "frontier_near_zero_and_mini_near_zero": "task-as-prompted still broken; do NOT accept DEAD; continue diagnosis",
    "frontier_scores_well_and_mini_near_zero": "DEAD is REAL and model-relative for gpt-4o-mini; accept with evidence"
  },
  "elapsed_s": 67.03163229999336,
  "summary": {
    "TEXT_TO_SQL": {
      "tasks": 5,
      "mean_phat": 0.0,
      "any_solve": false,
      "total_correct": 0,
      "total_candidates": 20
    },
    "STRUCTURED_EXTRACTION": {
      "tasks": 5,
      "mean_phat": 0.45,
      "any_solve": true,
      "total_correct": 9,
      "total_candidates": 20
    }
  },
  "rows": [
    {
      "task_id": "SQL-001",
      "domain": "TEXT_TO_SQL",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 0,
      "phat": 0.0,
      "status_counts": {
        "wrong": 4
      },
      "rendered_prompt_sha16": "18b8322e0583be68",
      "prompt_has_schema": true
    },
    {
      "task_id": "SQL-010",
      "domain": "TEXT_TO_SQL",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 0,
      "phat": 0.0,
      "status_counts": {
        "wrong": 4
      },
      "rendered_prompt_sha16": "294b312aeafa5ac5",
      "prompt_has_schema": true
    },
    {
      "task_id": "SQL-020",
      "domain": "TEXT_TO_SQL",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 0,
      "phat": 0.0,
      "status_counts": {
        "wrong": 4
      },
      "rendered_prompt_sha16": "3a59a85c64314e19",
      "prompt_has_schema": true
    },
    {
      "task_id": "SQL-030",
      "domain": "TEXT_TO_SQL",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 0,
      "phat": 0.0,
      "status_counts": {
        "wrong": 4
      },
      "rendered_prompt_sha16": "4afb09f168b23592",
      "prompt_has_schema": true
    },
    {
      "task_id": "SQL-040",
      "domain": "TEXT_TO_SQL",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 0,
      "phat": 0.0,
      "status_counts": {
        "wrong": 4
      },
      "rendered_prompt_sha16": "7e97b8f6a829257b",
      "prompt_has_schema": true
    },
    {
      "task_id": "EXT-001",
      "domain": "STRUCTURED_EXTRACTION",
      "model": "gpt-4o",
      "n": 4,
      "n_correct": 3,
      "phat": 0.75,
      "status_counts": {
        "pass": 3,
        "wrong": 1
      },
      "rendered_prompt_sha16": "694862c0fafc3576",
      "prompt_has_schema": true
    },
    {
      "task_id": "EXT-010",
   
```

### `apu_characterization\out\cap01\generation_config.json` size=3021
- format: JSON
- top keys: ['depth_triage', 'digest', 'endpoint', 'lock_phase', 'max_completion_tokens', 'model', 'prompt_template', 'prompt_template_sha256', 'prompt_templates', 'target_candidates', 'temperature', 'timeout_seconds']
- schema:
  - `depth_triage`: dict
  - `depth_triage.axis2_degeneracy`: dict
  - `depth_triage.axis2_degeneracy.definition`: str
  - `depth_triage.axis2_degeneracy.incorrect_duplicate_rate_max`: float
  - `depth_triage.calibration_escape_hatch`: dict
  - `depth_triage.calibration_escape_hatch.bounded_second_spend`: bool
  - `depth_triage.calibration_escape_hatch.rule`: str
  - `depth_triage.classification_error_disclosure`: str
  - `depth_triage.confirmation_pool_depth`: int
  - `depth_triage.lower_phat`: float
  - `depth_triage.protocol_amendment`: str
  - `depth_triage.scaling_pool_depth`: int
  - `depth_triage.stage1_informed_disclosure`: str
  - `depth_triage.triage_candidates`: int
  - `depth_triage.upper_phat`: float
  - `depth_triage.verifier_blocked_domains_full_depth`: list[empty] len=0
  - `digest`: str
  - `endpoint`: str
  - `lock_phase`: str
  - `max_completion_tokens`: int
  - `model`: str
  - `prompt_template`: str
  - `prompt_template_sha256`: str
  - `prompt_templates`: dict
  - `prompt_templates.CODE`: str
  - `prompt_templates.FUNCTION_CALLING`: str
  - `prompt_templates.MATH`: str
  - `prompt_templates.STRUCTURED_EXTRACTION`: str
  - `prompt_templates.TEXT_TO_SQL`: str
  - `target_candidates`: int
  - `temperature`: float
  - `timeout_seconds`: float
```json
{
  "depth_triage": {
    "axis2_degeneracy": {
      "definition": "Degenerate generation = (a) incorrect-only duplicate rate exceeding threshold, or (b) cross-task identical outputs. Convergent CORRECT answers on a single task are excluded.",
      "incorrect_duplicate_rate_max": 0.2
    },
    "calibration_escape_hatch": {
      "bounded_second_spend": true,
      "rule": "Any confirmation-pool task whose calibration curve contradicts its triage band is flagged; if the class flips to SCALING, top the pool up to scaling_pool_depth before classification freezes."
    },
    "classification_error_disclosure": "Triage-by-probe has a classification error rate; true-SCALING tasks near thresholds can draw extreme probe results and receive shallow pools. Mitigations: conservative thresholds, 256-not-zero confirmation pools, and calibration-time reclassification with top-up to 2048 if a confirmation-pool task flips to SCALING.",
    "confirmation_pool_depth": 256,
    "lower_phat": 0.02,
    "protocol_amendment": "cap01_v2.2_depth_triage",
    "scaling_pool_depth": 2048,
    "stage1_informed_disclosure": "Thresholds informed by Stage-1 probe verification (MATH-001 confidently-wrong identical; MATH-010 probable-SATURATED; MATH-025 intermediate). Full-corpus Stage-2 table was not read before this rule froze.",
    "triage_candidates": 16,
    "upper_phat": 0.9,
    "verifier_blocked_domains_full_depth": []
  },
  "digest": "6ac1952a8e376c79f3ebade131ee7b85e55a6e4856e69d0d233dcde46484cab9",
  "endpoint": "https://api.openai.com/v1/chat/completions",
  "lock_phase": "pre_generation",
  "max_completion_tokens": 4096,
  "model": "gpt-4o-mini",
  "prompt_template": "Solve the task below. Return only the proposed answer.\n\nDomain: {domain}\nTask:\n{prompt}\n",
  "prompt_template_sha256": "508607af3f492d08e6d6d6a39375e5a042706a8a2523b9a7060e1a3f2aa06567",
  "prompt_templates": {
    "CODE": "Return raw Python source only. Do not wrap the output in markdown code fences (no ```python, no ```) and do not include prose explanation before or after the code.\n\nDomain: {domain}\nTask:\n{prompt}",
    "FUNCTION_CALLING": "Return raw JSON only. Do not wrap the output in markdown code fences (no ```json, no ```). No prose.\n\nDomain: {domain}\nTask:\n{prompt}",
    "MATH": "Show one brief final calculation step, then give the final answer on its own line as 'Final answer: <value>'. No other prose. Do not wrap the output in markdown code fences.\n\nDomain: {domain}\nTask:\n{promp
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_base.json` size=390425
- parse error: Extra data: line 2 column 1 (char 1985)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_long_context.json` size=392016
- parse error: Extra data: line 2 column 1 (char 1993)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_func.json` size=401159
- parse error: Extra data: line 2 column 1 (char 2030)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_param.json` size=402974
- parse error: Extra data: line 2 column 1 (char 2181)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_base.json` size=78931
- parse error: Extra data: line 2 column 1 (char 438)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_long_context.json` size=114439
- parse error: Extra data: line 2 column 1 (char 446)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_func.json` size=80589
- parse error: Extra data: line 2 column 1 (char 447)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_param.json` size=80816
- parse error: Extra data: line 2 column 1 (char 448)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\possible_answer\BFCL_v4_multi_turn_composite.json` size=115938
- parse error: Extra data: line 2 column 1 (char 451)

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\question\BFCL_v4_multi_turn_composite.json` size=404501
- parse error: Extra data: line 2 column 1 (char 1714)

### `apu_characterization\out\cap01\perturbed_gold_audit.json` size=11522
- format: JSON
- top keys: ['summary', 'rows']
- schema:
  - `rows`: list[dict] len=25
  - `rows[].domain`: str
  - `rows[].gold_preview`: str
  - `rows[].pass`: bool
  - `rows[].perturbed_preview`: str
  - `rows[].status`: str
  - `rows[].task_id`: str
  - `summary`: dict
  - `summary.CODE`: dict
  - `summary.CODE.fail`: int
  - `summary.CODE.failures`: list[empty] len=0
  - `summary.CODE.healthy`: bool
  - `summary.CODE.n`: int
  - `summary.CODE.pass`: int
  - `summary.FUNCTION_CALLING`: dict
  - `summary.FUNCTION_CALLING.fail`: int
  - `summary.FUNCTION_CALLING.failures`: list[empty] len=0
  - `summary.FUNCTION_CALLING.healthy`: bool
  - `summary.FUNCTION_CALLING.n`: int
  - `summary.FUNCTION_CALLING.pass`: int
  - `summary.MATH`: dict
  - `summary.MATH.fail`: int
  - `summary.MATH.failures`: list[empty] len=0
  - `summary.MATH.healthy`: bool
  - `summary.MATH.n`: int
  - `summary.MATH.pass`: int
  - `summary.STRUCTURED_EXTRACTION`: dict
  - `summary.STRUCTURED_EXTRACTION.fail`: int
  - `summary.STRUCTURED_EXTRACTION.failures`: list[empty] len=0
  - `summary.STRUCTURED_EXTRACTION.healthy`: bool
  - `summary.STRUCTURED_EXTRACTION.n`: int
  - `summary.STRUCTURED_EXTRACTION.pass`: int
  - `summary.TEXT_TO_SQL`: dict
  - `summary.TEXT_TO_SQL.fail`: int
  - `summary.TEXT_TO_SQL.failures`: list[empty] len=0
  - `summary.TEXT_TO_SQL.healthy`: bool
  - `summary.TEXT_TO_SQL.n`: int
  - `summary.TEXT_TO_SQL.pass`: int
```json
{
  "summary": {
    "CODE": {
      "n": 5,
      "pass": 5,
      "fail": 0,
      "healthy": true,
      "failures": []
    },
    "FUNCTION_CALLING": {
      "n": 5,
      "pass": 5,
      "fail": 0,
      "healthy": true,
      "failures": []
    },
    "MATH": {
      "n": 5,
      "pass": 5,
      "fail": 0,
      "healthy": true,
      "failures": []
    },
    "STRUCTURED_EXTRACTION": {
      "n": 5,
      "pass": 5,
      "fail": 0,
      "healthy": true,
      "failures": []
    },
    "TEXT_TO_SQL": {
      "n": 5,
      "pass": 5,
      "fail": 0,
      "healthy": true,
      "failures": []
    }
  },
  "rows": [
    {
      "task_id": "SQL-001",
      "domain": "TEXT_TO_SQL",
      "pass": true,
      "status": "pass",
      "gold_preview": "SELECT COUNT(DISTINCT T2.School) FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Virtual = 'F' AND T1.AvgScrMath > 400",
      "perturbed_preview": "  SELECT COUNT(DISTINCT T2.School) from satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode\nwhere T2.Virtual = 'F' AND T1.AvgScrMath > 400  \n"
    },
    {
      "task_id": "SQL-002",
      "domain": "TEXT_TO_SQL",
      "pass": true,
      "status": "pass",
      "gold_preview": "SELECT T2.CDSCode FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.`Enrollment (K-12)` + T2.`Enrollment (Ages 5-17)` > 500",
      "perturbed_preview": "  SELECT T2.CDSCode from schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode\nwhere T2.`Enrollment (K-12)` + T2.`Enrollment (Ages 5-17)` > 500  \n"
    },
    {
      "task_id": "SQL-003",
      "domain": "TEXT_TO_SQL",
      "pass": true,
      "status": "pass",
      "gold_preview": "SELECT MAX(CAST(T1.`Free Meal Count (Ages 5-17)` AS REAL) / T1.`Enrollment (Ages 5-17)`) FROM frpm AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE",
      "perturbed_preview": "  SELECT MAX(CAST(T1.`Free Meal Count (Ages 5-17)` AS REAL) / T1.`Enrollment (Ages 5-17)`) from frpm AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds\nwhe"
    },
    {
      "task_id": "SQL-004",
      "domain": "TEXT_TO_SQL",
      "pass": true,
      "status": "pass",
      "gold_preview": "SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS WritingScoreRank FROM schools AS T1  INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cd",
      "perturbed_preview": "  SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS WritingScoreRank fr
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-001.jsonl` size=2481
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-13d1f8ba8a992976a6ec911b",
  "completion_tokens": 129,
  "content": "{\n  \"menu\": {\n    \"cnt\": \"2\",\n    \"itemsubtotal\": \"60.000\",\n    \"nm\": \"-TICKET CP\",\n    \"num\": \"901016\",\n    \"price\": \"60.000\"\n  },\n  \"sub_total\": {\n    \"discount_price\": \"-60.000\",\n    \"subtotal_price\": \"60.000\",\n    \"tax_price\": \"5.455\"\n  },\n  \"total\": {\n    \"creditcardprice\": \"60.000\",\n    \"menuqty_cnt\": \"2.00\",\n    \"total_price\": \"60.000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7FdYmTvKpLWheejQ1OxHH7EuQw",
  "ordinal": 0,
  "prompt_tokens": 580,
  "task_id": "EXT-001"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-0a1cdb0b2a3498f83b5f0a77",
  "completion_tokens": 127,
  "content": "{\n  \"menu\": {\n    \"cnt\": \"2\",\n    \"itemsubtotal\": \"60.000\",\n    \"nm\": \"-TICKET CP\",\n    \"num\": \"901016\",\n    \"price\": \"60.000\"\n  },\n  \"sub_total\": {\n    \"discount_price\": \"-60.000\",\n    \"subtotal_price\": \"60.000\",\n    \"tax_price\": \"5.455\"\n  },\n  \"total\": {\n    \"creditcardprice\": \"60.000\",\n    \"menuqty_cnt\": \"2\",\n    \"total_price\": \"60.000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7HqbEOvZ1ZKbEtKENQFdkXBg5q",
  "ordinal": 1,
  "prompt_tokens": 580,
  "task_id": "EXT-001"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-7377254f3c0cac9dc99942f2",
  "completion_tokens": 129,
  "content": "{\n  \"menu\": {\n    \"cnt\": \"2\",\n    \"itemsubtotal\": \"60.000\",\n    \"nm\": \"-TICKET CP\",\n    \"num\": \"901016\",\n    \"price\": \"60.000\"\n  },\n  \"sub_total\": {\n    \"discount_price\": \"-60.000\",\n    \"subtotal_price\": \"60.000\",\n    \"tax_price\": \"5.455\"\n  },\n  \"total\": {\n    \"creditcardprice\": \"60.000\",\n    \"menuqty_cnt\": \"2.00\",\n    \"total_price\": \"60.000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7IJ1g9K4PKrR7rGNFvJ9MdTqSX",
  "ordinal": 2,
  "prompt_tokens": 580,
  "task_id": "EXT-001"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-010.jsonl` size=1864
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-78261b6d53b13b1b9f9d3053",
  "completion_tokens": 82,
  "content": "{\n  \"menu\": {\n    \"nm\": \"Bumbu Kaldu Ayam 1\",\n    \"price\": \"36000\",\n    \"unitprice\": \"36000\"\n  },\n  \"sub_total\": {\n    \"subtotal_price\": \"36000\"\n  },\n  \"total\": {\n    \"cashprice\": \"50000\",\n    \"changeprice\": \"14000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7LHRu5NQPLMPAiw5waGyVuncKq",
  "ordinal": 0,
  "prompt_tokens": 430,
  "task_id": "EXT-010"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-1f6171d4ab96416e98994bb8",
  "completion_tokens": 82,
  "content": "{\n  \"menu\": {\n    \"nm\": \"Bumbu Kaldu Ayam 1\",\n    \"price\": \"36000\",\n    \"unitprice\": \"36000\"\n  },\n  \"sub_total\": {\n    \"subtotal_price\": \"36000\"\n  },\n  \"total\": {\n    \"cashprice\": \"50000\",\n    \"changeprice\": \"14000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7Mf7jO0C410sq8ho6AO4iT0y6n",
  "ordinal": 1,
  "prompt_tokens": 430,
  "task_id": "EXT-010"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-df2dd4b781ff9d4a045e892d",
  "completion_tokens": 82,
  "content": "{\n  \"menu\": {\n    \"nm\": \"Bumbu Kaldu Ayam 1\",\n    \"price\": \"36000\",\n    \"unitprice\": \"36000\"\n  },\n  \"sub_total\": {\n    \"subtotal_price\": \"36000\"\n  },\n  \"total\": {\n    \"cashprice\": \"50000\",\n    \"changeprice\": \"14000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7NZ3hR1iWElCKcYgJOlPFzTJtf",
  "ordinal": 2,
  "prompt_tokens": 430,
  "task_id": "EXT-010"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-020.jsonl` size=2362
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-0c38caa6dd77b905aa21458e",
  "completion_tokens": 123,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"4\",\n      \"nm\": \"AMBUSH DBL CHS\",\n      \"price\": \"60000\"\n    },\n    {\n      \"cnt\": \"10\",\n      \"nm\": \"AMBUSH CHS BUR\",\n      \"price\": \"100000\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"NET SALES 160000\",\n    \"tax_price\": \"TAX 16000\"\n  },\n  \"total\": {\n    \"total_price\": \"AMOUNT DUE 176000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7PXPc6BmhZo3qsdl4l4iZx9SuT",
  "ordinal": 0,
  "prompt_tokens": 457,
  "task_id": "EXT-020"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-42944c335be88a3d75d779b1",
  "completion_tokens": 112,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"4\",\n      \"nm\": \"AMBUSH DBL CHS\",\n      \"price\": \"60000\"\n    },\n    {\n      \"cnt\": \"10\",\n      \"nm\": \"AMBUSH CHS BUR\",\n      \"price\": \"100000\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"160000\",\n    \"tax_price\": \"16000\"\n  },\n  \"total\": {\n    \"total_price\": \"176000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7RVrFpK9f4r2hQHFgTGXho6YLY",
  "ordinal": 1,
  "prompt_tokens": 457,
  "task_id": "EXT-020"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-b4adb5df647cb5a7d89bf7f6",
  "completion_tokens": 123,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"4\",\n      \"nm\": \"AMBUSH DBL CHS\",\n      \"price\": \"60000\"\n    },\n    {\n      \"cnt\": \"10\",\n      \"nm\": \"AMBUSH CHS BUR\",\n      \"price\": \"100000\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"NET SALES 160000\",\n    \"tax_price\": \"TAX 16000\"\n  },\n  \"total\": {\n    \"total_price\": \"AMOUNT DUE 176000\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7SI5flpmcBDHjWQTotdCOEKlBt",
  "ordinal": 2,
  "prompt_tokens": 457,
  "task_id": "EXT-020"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-030.jsonl` size=4100
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-cbd9577a1d2092a1338a8a02",
  "completion_tokens": 256,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"COLD OCHA\",\n      \"price\": \"10,909\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"BCA PROMO\",\n      \"price\": \"54,455\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED SHUMAI\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED TOFU ROLL\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"EBI TEMPURA\",\n      \"price\": \"13,636\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"KITSUNE UDON (KIDS)\",\n      \"price\": \"28,182\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"132,636\",\n    \"tax_price\": \"13,264\"\n  },\n  \"total\": {\n    \"total_price\": \"145,900\",\n    \"creditcardprice\": \"145,900\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7Xwzc1lk9RefoQfwSU4LtavNiI",
  "ordinal": 0,
  "prompt_tokens": 658,
  "task_id": "EXT-030"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-7c0b229de8978a293727abb0",
  "completion_tokens": 256,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"COLD OCHA\",\n      \"price\": \"10,909\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"BCA PROMO\",\n      \"price\": \"54,455\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED SHUMAI\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED TOFU ROLL\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"EBI TEMPURA\",\n      \"price\": \"13,636\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"KITSUNE UDON (KIDS)\",\n      \"price\": \"28,182\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"132,636\",\n    \"tax_price\": \"13,264\"\n  },\n  \"total\": {\n    \"total_price\": \"145,900\",\n    \"creditcardprice\": \"145,900\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7ZUv2KAx84oQeoQsvEQzx7cHot",
  "ordinal": 1,
  "prompt_tokens": 658,
  "task_id": "EXT-030"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-27b582b5ec1a0d88a447a2a9",
  "completion_tokens": 256,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"COLD OCHA\",\n      \"price\": \"10,909\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"BCA PROMO\",\n      \"price\": \"54,455\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED SHUMAI\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"SKEWERED TOFU ROLL\",\n      \"price\": \"12,727\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"EBI TEMPURA\",\n      \"price\": \"13,636\"\n    },\n    {\n      \"cnt\": \"1\",\n      \"nm\": \"KITSUNE UDON (KIDS)\",\n      \"price\": \"28,182\"\n    }\n  ],\n  \"sub_total\": {\n    \"subtotal_price\": \"132,636\",\n    \"tax_price\": \"13,264\"\n  },\n  \"total\": {\n    \"total_price\": \"145,900\",\n    \"creditcardprice\": \"145,900\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7bdZVMAIB1KYuOJqYmmDMgp1y5",
  "ordinal": 2,
  "prompt_tokens": 658,
  "task_id": "EXT-030"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-040.jsonl` size=4194
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-434b34f833005878f5db18f5",
  "completion_tokens": 261,
  "content": "{\n  \"menu\": [\n    {\n      \"num\": \"HPL754DR\",\n      \"nm\": \"LUNCH BOX 3P SET W/RED BAG & SP00 N.\",\n      \"cnt\": \"8 PCS\",\n      \"unitprice\": \"243,000\",\n      \"price\": \"1,944,000\",\n      \"itemsubtotal\": \"1,555,200\"\n    },\n    {\n      \"num\": \"HPL500\",\n      \"nm\": \"RICE CASE 7L W/CUP\",\n      \"cnt\": \"5 PCS\",\n      \"unitprice\": \"195,000\",\n      \"price\": \"975,000\",\n      \"itemsubtotal\": \"780,000\"\n    },\n    {\n      \"num\": \"HPL754DB\",\n      \"nm\": \"LUNCH BOX 3P SET W/BLACK BAG & SP OON\",\n      \"cnt\": \"4 PCS\",\n      \"unitprice\": \"243,000\",\n      \"price\": \"972,000\",\n      \"itemsubtotal\": \"777,600\"\n    }\n  ],\n  \"total\": {\n    \"menutype_cnt\": \"3\",\n    \"menuqty_cnt\": \"17\",\n    \"creditcardprice\": \"3,112,800\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7gpcL3gijnr0A5p1OkIyxyuYSZ",
  "ordinal": 0,
  "prompt_tokens": 656,
  "task_id": "EXT-040"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-920a787e8ee9ec90caf1a116",
  "completion_tokens": 274,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"8 PCS\",\n      \"itemsubtotal\": \"1,555,200\",\n      \"nm\": \"LUNCH BOX 3P SET W/RED BAG & SP00 N.\",\n      \"num\": \"HPL754DR\",\n      \"price\": \"1,944,000\",\n      \"unitprice\": \"243,000\"\n    },\n    {\n      \"cnt\": \"5 PCS\",\n      \"itemsubtotal\": \"780,000\",\n      \"nm\": \"RICE CASE 7L W/CUP\",\n      \"num\": \"HPL500\",\n      \"price\": \"975,000\",\n      \"unitprice\": \"195,000\"\n    },\n    {\n      \"cnt\": \"4 PCS\",\n      \"itemsubtotal\": \"777,600\",\n      \"nm\": \"LUNCH BOX 3P SET W/BLACK BAG & SP OON\",\n      \"num\": \"HPL754DB\",\n      \"price\": \"972,000\",\n      \"unitprice\": \"243,000\"\n    }\n  ],\n  \"total\": {\n    \"creditcardprice\": \"BAYAR CREDIT CARD 3,112,800\",\n    \"menuqty_cnt\": \"TOTAL QTY 17\",\n    \"menutype_cnt\": \"TOTAL ITEM 3\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7imXNZriU5kRmwcHvxTeOxES4t",
  "ordinal": 1,
  "prompt_tokens": 656,
  "task_id": "EXT-040"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-1c12abaccca62a5ab0f95b05",
  "completion_tokens": 274,
  "content": "{\n  \"menu\": [\n    {\n      \"cnt\": \"8 PCS\",\n      \"itemsubtotal\": \"1,555,200\",\n      \"nm\": \"LUNCH BOX 3P SET W/RED BAG & SP00 N.\",\n      \"num\": \"HPL754DR\",\n      \"price\": \"1,944,000\",\n      \"unitprice\": \"243,000\"\n    },\n    {\n      \"cnt\": \"5 PCS\",\n      \"itemsubtotal\": \"780,000\",\n      \"nm\": \"RICE CASE 7L W/CUP\",\n      \"num\": \"HPL500\",\n      \"price\": \"975,000\",\n      \"unitprice\": \"195,000\"\n    },\n    {\n      \"cnt\": \"4 PCS\",\n      \"itemsubtotal\": \"777,600\",\n      \"nm\": \"LUNCH BOX 3P SET W/BLACK BAG & SP OON\",\n      \"num\": \"HPL754DB\",\n      \"price\": \"972,000\",\n      \"unitprice\": \"243,000\"\n    }\n  ],\n  \"total\": {\n    \"creditcardprice\": \"BAYAR CREDIT CARD 3,112,800\",\n    \"menuqty_cnt\": \"TOTAL QTY 17\",\n    \"menutype_cnt\": \"TOTAL ITEM 3\"\n  }\n}",
  "generation_request_id": "chatcmpl-E1x7l1VUud4WEZtodAuRKk13Vchga",
  "ordinal": 2,
  "prompt_tokens": 656,
  "task_id": "EXT-040"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-SQL-001.jsonl` size=1285
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-533a3ade004fee377c2ec235",
  "completion_tokens": 35,
  "content": "SELECT COUNT(*) FROM schools s JOIN satscores ss ON s.CDSCode = ss.cds WHERE ss.AvgScrMath > 400 AND s.Virtual = 'F';",
  "generation_request_id": "chatcmpl-E1x6m5dGMCDwkaitAqKRUuV9A8SID",
  "ordinal": 0,
  "prompt_tokens": 995,
  "task_id": "SQL-001"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-1b72790a9ed2e171f5597c46",
  "completion_tokens": 38,
  "content": "SELECT COUNT(*)\nFROM schools s\nJOIN satscores ss ON s.CDSCode = ss.cds\nWHERE ss.AvgScrMath > 400 AND s.Virtual = 'F';",
  "generation_request_id": "chatcmpl-E1x6meFGM4R3ye2s05Ib7FGMbgDma",
  "ordinal": 1,
  "prompt_tokens": 995,
  "task_id": "SQL-001"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-097bb2d52451e27dc6f4fcc1",
  "completion_tokens": 35,
  "content": "SELECT COUNT(*) FROM satscores s JOIN schools sc ON s.cds = sc.CDSCode WHERE s.AvgScrMath > 400 AND sc.Virtual = 'F';",
  "generation_request_id": "chatcmpl-E1x6nXRzW5GpoEkZxudSUgpLhSTiE",
  "ordinal": 2,
  "prompt_tokens": 995,
  "task_id": "SQL-001"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-SQL-010.jsonl` size=2251
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-5a09491be7624215ea948166",
  "completion_tokens": 135,
  "content": "SELECT s.School, s.DOCType\nFROM frpm f\nJOIN schools s ON f.CDSCode = s.CDSCode\nWHERE s.FundingType = 'Locally Funded'\nAND (f.`Enrollment (K-12)` - f.`Enrollment (Ages 5-17)`) > \n  (\n    SELECT AVG(f2.`Enrollment (K-12)` - f2.`Enrollment (Ages 5-17)`)\n    FROM frpm f2\n    JOIN schools s2 ON f2.CDSCode = s2.CDSCode\n    WHERE s2.FundingType = 'Locally Funded'\n  );",
  "generation_request_id": "chatcmpl-E1x6q8XuGKFQGfXmKLFSegcc7s1RC",
  "ordinal": 0,
  "prompt_tokens": 1037,
  "task_id": "SQL-010"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-eef01083af05ef498c7c3712",
  "completion_tokens": 128,
  "content": "SELECT s.School, s.DOCType \nFROM schools s\nJOIN frpm f ON s.CDSCode = f.CDSCode\nWHERE s.FundingType = 'Local' \nAND (f.`Enrollment (K-12)` - f.`Enrollment (Ages 5-17)`) > \n    (SELECT AVG(f1.`Enrollment (K-12)` - f1.`Enrollment (Ages 5-17)`) \n     FROM schools s1\n     JOIN frpm f1 ON s1.CDSCode = f1.CDSCode \n     WHERE s1.FundingType = 'Local');",
  "generation_request_id": "chatcmpl-E1x6sIcRqge0QCi2R0JCXskEPdnUb",
  "ordinal": 1,
  "prompt_tokens": 1037,
  "task_id": "SQL-010"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-2f3cb262b06c9c18ac2aef88",
  "completion_tokens": 129,
  "content": "SELECT s.School, s.DOCType \nFROM schools s \nJOIN frpm f ON s.CDSCode = f.CDSCode \nWHERE s.FundingType = 'Locally Funded' \nAND (f.`Enrollment (K-12)` - f.`Enrollment (Ages 5-17)`) > (\n    SELECT AVG(`Enrollment (K-12)` - `Enrollment (Ages 5-17)`)\n    FROM frpm f2 \n    JOIN schools s2 ON f2.CDSCode = s2.CDSCode \n    WHERE s2.FundingType = 'Locally Funded'\n);",
  "generation_request_id": "chatcmpl-E1x6teXaVe3mR3jRWjJco7edE3d9u",
  "ordinal": 2,
  "prompt_tokens": 1037,
  "task_id": "SQL-010"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-SQL-020.jsonl` size=1401
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-3f24157099c9ad288506229b",
  "completion_tokens": 48,
  "content": "SELECT COUNT(*) / 12 AS monthly_average FROM schools WHERE County = 'Alameda' AND DOC = '52' AND OpenDate >= '1980-01-01' AND OpenDate < '1981-01-01';",
  "generation_request_id": "chatcmpl-E1x6z4g6SOsEypxVP8htImZVmhQTu",
  "ordinal": 0,
  "prompt_tokens": 1027,
  "task_id": "SQL-020"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-23da04fb59e649139c96e2e5",
  "completion_tokens": 45,
  "content": "SELECT COUNT(*) / 12 AS monthly_average FROM schools WHERE County = 'Alameda' AND DOC = '52' AND OpenDate BETWEEN '1980-01-01' AND '1980-12-31';",
  "generation_request_id": "chatcmpl-E1x70ULCy5HsNXpgPB8oT27OayDDf",
  "ordinal": 1,
  "prompt_tokens": 1027,
  "task_id": "SQL-020"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-cedf12c78ee363096bc1609a",
  "completion_tokens": 38,
  "content": "SELECT COUNT(*) / 12 AS monthly_average_opened_schools FROM schools WHERE County = 'Alameda' AND DOC = '52' AND OpenDate LIKE '1980%';",
  "generation_request_id": "chatcmpl-E1x71sOqDqp7wIz6eXpSBdY36AZs5",
  "ordinal": 2,
  "prompt_tokens": 1027,
  "task_id": "SQL-020"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-SQL-030.jsonl` size=1805
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-809dd910e6fb2c6cfd11b4a3",
  "completion_tokens": 91,
  "content": "SELECT AdmEmail1, AdmEmail2, AdmEmail3 \nFROM schools \nWHERE County = 'San Bernardino' \nAND City = 'San Bernardino' \nAND OpenDate BETWEEN '2009-01-01' AND '2010-12-31' \nAND (SOC = '62' OR DOC = '54') \nAND (AdmEmail1 IS NOT NULL OR AdmEmail2 IS NOT NULL OR AdmEmail3 IS NOT NULL);",
  "generation_request_id": "chatcmpl-E1x73ZFKZCaEvP21KKbJbs7jG62OR",
  "ordinal": 0,
  "prompt_tokens": 1071,
  "task_id": "SQL-030"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-104a250a65ad6035c01e672a",
  "completion_tokens": 87,
  "content": "SELECT AdmEmail1 \nFROM schools \nWHERE County = 'San Bernardino' \n  AND City = 'San Bernardino City Unified' \n  AND OpenDate BETWEEN '2009-01-01' AND '2010-12-31' \n  AND ((SOC = '62' AND DOC = '54') OR (SOC = '54' AND DOC = '54')) \n  AND AdmEmail1 IS NOT NULL;",
  "generation_request_id": "chatcmpl-E1x752UxWCdZAOEdMjVRau8RLrXTJ",
  "ordinal": 1,
  "prompt_tokens": 1071,
  "task_id": "SQL-030"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-58b01dfbe0d9ca085cdf1f45",
  "completion_tokens": 74,
  "content": "SELECT AdmEmail1 \nFROM schools \nWHERE County = 'San Bernardino' \nAND City = 'San Bernardino' \nAND DOC IN ('54') \nAND SOC IN ('62') \nAND DATE(OpenDate) BETWEEN '2009-01-01' AND '2010-12-31'\nAND (SOC IN ('62') OR DOC IN ('54'));",
  "generation_request_id": "chatcmpl-E1x76qVe85mEcmmPKDv7JFRQhvu4A",
  "ordinal": 2,
  "prompt_tokens": 1071,
  "task_id": "SQL-030"
}
```

### `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-SQL-040.jsonl` size=1923
- format: JSONL records=4
- top-level keys (first 20 rows union): ['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
- schema[0]:
  - `candidate_id`: str
  - `completion_tokens`: int
  - `content`: str
  - `generation_request_id`: str
  - `ordinal`: int
  - `prompt_tokens`: int
  - `task_id`: str
### sample[0]
```json
{
  "candidate_id": "cand-66c876b4146e14f93f7c2a70",
  "completion_tokens": 79,
  "content": "SELECT (COUNT(CASE WHEN c.gender = 'M' THEN 1 END) * 100.0 / COUNT(*)) AS male_percentage FROM client c JOIN district d ON c.district_id = d.district_id WHERE d.A3 = 'south Bohemia' AND d.A4 = (SELECT MAX(A4) FROM district WHERE A3 = 'south Bohemia');",
  "generation_request_id": "chatcmpl-E1x78wCNT2MSJqCXaPa3IBlg5RiDe",
  "ordinal": 0,
  "prompt_tokens": 783,
  "task_id": "SQL-040"
}
```

### sample[1]
```json
{
  "candidate_id": "cand-c7393f25fcc788f01d1ec816",
  "completion_tokens": 89,
  "content": "SELECT (COUNT(CASE WHEN c.gender = 'M' THEN 1 END) * 100.0) / COUNT(c.client_id) AS percentage_male_clients\nFROM client c\nJOIN district d ON c.district_id = d.district_id\nWHERE d.A3 = 'south Bohemia' AND d.A4 = (\n    SELECT MAX(A4) FROM district WHERE A3 = 'south Bohemia'\n);",
  "generation_request_id": "chatcmpl-E1x7ADcPZS3gvd89IOVMmfuxnowNQ",
  "ordinal": 1,
  "prompt_tokens": 783,
  "task_id": "SQL-040"
}
```

### sample[2]
```json
{
  "candidate_id": "cand-fd80b41efdb49ce4c4a333d8",
  "completion_tokens": 81,
  "content": "SELECT (COUNT(CASE WHEN client.gender = 'M' THEN 1 END) * 100.0 / COUNT(*)) AS male_percentage\nFROM client\nJOIN district ON client.district_id = district.district_id\nWHERE district.A3 LIKE '%south Bohemia%'\nAND district.A4 = (SELECT MAX(A4) FROM district WHERE A3 LIKE '%south Bohemia%');",
  "generation_request_id": "chatcmpl-E1x7CzHO70E0N5agHgslbg8vh6WJ4",
  "ordinal": 2,
  "prompt_tokens": 783,
  "task_id": "SQL-040"
}
```

### `apu_characterization\out\cap01\probe_verification_stage1.json` size=3540
- format: JSON
- record_count: 10
- schema[0]:
  - `batch`: str
  - `domain`: str
  - `n`: int
  - `n_correct`: int
  - `phat`: float
  - `provisional`: str
  - `statuses`: list[str] len=8
  - `task_id`: str
  - `unique`: int
### sample[0]
```json
{
  "batch": "v2",
  "task_id": "CODE-001",
  "domain": "CODE",
  "n": 8,
  "n_correct": 0,
  "phat": 0.0,
  "unique": 6,
  "statuses": [
    "wrong",
    "wrong",
    "wrong",
    "wrong",
    "wrong",
    "wrong",
    "wrong",
    "wrong"
  ],
  "provisional": "probable-DEAD"
}
```

### sample[1]
```json
{
  "batch": "v2",
  "task_id": "FC-001",
  "domain": "FUNCTION_CALLING",
  "n": 8,
  "n_correct": 0,
  "phat": 0.0,
  "unique": 2,
  "statuses": [
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid"
  ],
  "provisional": "probable-DEAD"
}
```

### sample[2]
```json
{
  "batch": "v2",
  "task_id": "SQL-001",
  "domain": "TEXT_TO_SQL",
  "n": 8,
  "n_correct": 0,
  "phat": 0.0,
  "unique": 7,
  "statuses": [
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid",
    "invalid"
  ],
  "provisional": "probable-DEAD"
}
```

### `apu_characterization\out\cap01\prompt_completeness_audit.json` size=37483
- format: JSON
- top keys: ['sql_verdict', 'ext_verdict', 'sql_missing', 'ext_missing', 'sql_root_cause', 'ext_root_cause', 'samples']
- schema:
  - `ext_missing`: NoneType
  - `ext_root_cause`: str
  - `ext_verdict`: str
  - `samples`: list[dict] len=10
  - `samples[].corpus_prompt_preview`: str
  - `samples[].domain`: str
  - `samples[].missing_element`: NoneType
  - `samples[].prompt_complete`: bool
  - `samples[].rendered_prompt`: str
  - `samples[].root_cause`: str
  - `samples[].task_id`: str
  - `samples[].verifier_has_schema_asset`: bool
  - `sql_missing`: NoneType
  - `sql_root_cause`: str
  - `sql_verdict`: str
```json
{
  "sql_verdict": "PROMPT COMPLETE",
  "ext_verdict": "PROMPT COMPLETE",
  "sql_missing": null,
  "ext_missing": null,
  "sql_root_cause": "ok",
  "ext_root_cause": "ok",
  "samples": [
    {
      "task_id": "SQL-001",
      "domain": "TEXT_TO_SQL",
      "rendered_prompt": "Return the raw SQL statement only. Do not wrap the output in markdown code fences (no ```sql, no ```). No prose.\n\nDomain: TEXT_TO_SQL\nTask:\nHow many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual?\n\nEvidence: Exclusively virtual refers to Virtual = 'F'\n\nDatabase: california_schools\nSchema:\nCREATE TABLE frpm\n(\n    CDSCode                                       TEXT not null\n        primary key,\n    `Academic Year`                               TEXT  null,\n    `County Code`                                 TEXT  null,\n    `District Code`                               INTEGER         null,\n    `School Code`                                 TEXT  null,\n    `County Name`                                 TEXT null,\n    `District Name`                               TEXT null,\n    `School Name`                                 TEXT null,\n    `District Type`                               TEXT null,\n    `School Type`                                 TEXT null,\n    `Educational Option Type`                     TEXT null,\n    `NSLP Provision Status`                       TEXT null,\n    `Charter School (Y/N)`                        INTEGER    null,\n    `Charter School Number`                       TEXT  null,\n    `Charter Funding Type`                        TEXT null,\n    IRC                                           INTEGER    null,\n    `Low Grade`                                   TEXT  null,\n    `High Grade`                                  TEXT null,\n    `Enrollment (K-12)`                           REAL      null,\n    `Free Meal Count (K-12)`                      REAL       null,\n    `Percent (%) Eligible Free (K-12)`            REAL       null,\n    `FRPM Count (K-12)`                           REAL       null,\n    `Percent (%) Eligible FRPM (K-12)`            REAL       null,\n    `Enrollment (Ages 5-17)`                      REAL       null,\n    `Free Meal Count (Ages 5-17)`                 REAL       null,\n    `Percent (%) Eligible Free (Ages 5-17)`       REAL       null,\n    `FRPM Count (Ages 5-17)`                      REAL       null,\n    `Percent (%) Eligible FRPM (Ages 5-17)`       REAL       null,\n    
```

### `apu_characterization\out\cap01\protocol_cap01_v2.locked.json` size=14240
- format: JSON
- top keys: ['amendment', 'budget', 'budget_framing', 'calibration', 'candidate_pool', 'claim_ladder', 'claim_under_test', 'corpus', 'energy_variant', 'experiment', 'floor_anchor', 'gates', 'latency_backend', 'lock_fields', 'lock_phase', 'locked_population', 'locked_schedule', 'matrix', 'pre_p2_flags', 'pre_registered_null', 'projection', 'protocol_version', 'schedule_estimate', 'statistics', 'status', 'supersedes', 'validity_class', 'verifiers']
- schema:
  - `amendment`: str
  - `budget`: dict
  - `budget.candidate_counts_when`: str
  - `budget.clock`: str
  - `budget.in_flight_at_deadline`: str
  - `budget.max_violating_task_cell_fraction`: float
  - `budget.setup_in_primary_budget`: bool
  - `budget.start_barrier`: str
  - `budget.wall_overshoot_fraction`: float
  - `budget_framing`: str
  - `calibration`: dict
  - `calibration.below_minimum_action`: str
  - `calibration.dead_rule`: dict
  - `calibration.dead_rule.n`: int
  - `calibration.dead_rule.probability_lt`: float
  - `calibration.freeze_scope`: str
  - `calibration.legacy_dead_context`: dict
  - `calibration.legacy_dead_context.analysis_role`: str
  - `calibration.legacy_dead_context.n`: int
  - `calibration.legacy_dead_context.probability_lt`: float
  - `calibration.minimum_scaling_tasks_per_domain`: int
  - `calibration.primary_population`: str
  - `calibration.saturated_rule`: dict
  - `calibration.saturated_rule.n`: int
  - `calibration.saturated_rule.probability_gt`: float
  - `calibration.secondary_population`: str
  - `calibration.shuffles`: int
  - `candidate_pool`: dict
  - `candidate_pool.blind_to_harness`: bool
  - `candidate_pool.candidate_order`: str
  - `candidate_pool.depth_triage`: dict
  - `candidate_pool.depth_triage.axis2_degeneracy`: dict
  - `candidate_pool.depth_triage.axis2_degeneracy.convergent_correct_excluded`: bool
  - `candidate_pool.depth_triage.axis2_degeneracy.cross_task_identical_outputs`: str
  - `candidate_pool.depth_triage.axis2_degeneracy.incorrect_duplicate_rate_max`: float
  - `candidate_pool.depth_triage.calibration_escape_hatch`: dict
  - `candidate_pool.depth_triage.calibration_escape_hatch.bounded_second_spend`: bool
  - `candidate_pool.depth_triage.calibration_escape_hatch.top_up_to_scaling_on_flip_to_SCALING`: bool
  - `candidate_pool.depth_triage.confirmation_pool_depth`: int
  - `candidate_pool.depth_triage.enabled`: bool
  - `candidate_pool.depth_triage.lower_phat`: float
  - `candidate_pool.depth_triage.scaling_pool_depth`: int
  - `candidate_pool.depth_triage.triage_candidates`: int
  - `candidate_pool.depth_triage.upper_phat`: float
  - `candidate_pool.depth_triage.verifier_blocked_domains_full_depth`: list[str] len=1
  - `candidate_pool.generation_backend`: str
  - `candidate_pool.hash_algorithm`: str
  - `candidate_pool.minimum_candidates_per_task`: int
  - `candidate_pool.pool_exhaustion`: str
  - `candidate_pool.required_manifest_fields`: list[str] len=5
  - `candidate_pool.seed_namespace`: str
  - `candidate_pool.surviving_v1_pools`: str
  - `claim_ladder`: dict
  - `claim_ladder.rung_1`: str
  - `claim_ladder.rung_2`: str
  - `claim_ladder.rung_3`: str
  - `claim_under_test`: str
  - `corpus`: dict
  - `corpus.contamination_policy`: str
  - `corpus.deferred_scopes`: dict
  - `corpus.deferred_scopes.bfcl_multi_turn_subset`: str
  - `corpus.deferred_scopes.bird_interactive_mode`: str
  - `corpus.deferred_scopes.tau2_bench_multi_turn_service_tasks`: str
  - `corpus.deferred_scopes.terminal_bench_multi_step_shell_tasks`: str
  - `corpus.domains`: dict
  - `corpus.domains.CODE`: dict
  - `corpus.domains.CODE.candidate`: str
  - `corpus.domains.CODE.domain_id`: str
  - `corpus.domains.CODE.primary_tier_ms`: int
  - `corpus.domains.CODE.report_rationale`: str
  - `corpus.domains.CODE.scope_restriction`: str
  - `corpus.domains.CODE.source`: str
  - `corpus.domains.CODE.verifier`: str
  - `corpus.domains.FUNCTION_CALLING`: dict
  - `corpus.domains.FUNCTION_CALLING.candidate`: str
  - `corpus.domains.FUNCTION_CALLING.domain_id`: str
  - `corpus.domains.FUNCTION_CALLING.primary_tier_ms`: int
  - `corpus.domains.FUNCTION_CALLING.report_rationale`: str
  - `corpus.domains.FUNCTION_CALLING.scope_restriction`: str
  - `corpus.domains.FUNCTION_CALLING.source`: str
```json
{
  "amendment": "cap01_v2.2_depth_triage",
  "budget": {
    "candidate_counts_when": "verifier_verdict_before_deadline",
    "clock": "CLOCK_MONOTONIC",
    "in_flight_at_deadline": "abandoned",
    "max_violating_task_cell_fraction": 0.01,
    "setup_in_primary_budget": false,
    "start_barrier": "task_ready_after_session_setup",
    "wall_overshoot_fraction": 0.02
  },
  "budget_framing": "The fixed budget represents a resource ceiling \u2014 the compute/time allocation a production system grants a verifiable task \u2014 not user wait-time tolerance. The energy variant is the same ceiling denominated in joules. The claim under test is: under a fixed allocation, a lower orchestration floor converts the identical allocation into more solved tasks.",
  "calibration": {
    "below_minimum_action": "flag_before_P2_and_require_explicit_protocol_amendment",
    "dead_rule": {
      "n": 2048,
      "probability_lt": 0.05
    },
    "freeze_scope": "once_after_all_five_domain_pools_exist",
    "legacy_dead_context": {
      "analysis_role": "secondary_context_only",
      "n": 128,
      "probability_lt": 0.05
    },
    "minimum_scaling_tasks_per_domain": 20,
    "primary_population": "SCALING",
    "saturated_rule": {
      "n": 4,
      "probability_gt": 0.9
    },
    "secondary_population": "ALL",
    "shuffles": 50
  },
  "candidate_pool": {
    "blind_to_harness": true,
    "candidate_order": "sha256_seeded_fisher_yates",
    "depth_triage": {
      "axis2_degeneracy": {
        "convergent_correct_excluded": true,
        "cross_task_identical_outputs": "fail",
        "incorrect_duplicate_rate_max": 0.2
      },
      "calibration_escape_hatch": {
        "bounded_second_spend": true,
        "top_up_to_scaling_on_flip_to_SCALING": true
      },
      "confirmation_pool_depth": 256,
      "enabled": true,
      "lower_phat": 0.02,
      "scaling_pool_depth": 2048,
      "triage_candidates": 16,
      "upper_phat": 0.9,
      "verifier_blocked_domains_full_depth": [
        "CODE"
      ]
    },
    "generation_backend": "openai",
    "hash_algorithm": "sha256",
    "minimum_candidates_per_task": 2048,
    "pool_exhaustion": "hard_gate_failure",
    "required_manifest_fields": [
      "generation_model",
      "temperature",
      "prompt_template_sha256",
      "candidate_token_counts",
      "task_pool_sha256"
    ],
    "seed_namespace": "cap01_v1",
    "surviving_v1_pools": "keep_only_for_tasks_surviving_the_v2_cut; never_regenerate"
  },
  "claim
```

### `apu_characterization\out\cap01\stage345_report.json` size=25598
- format: JSON
- top keys: ['axis2', 'calibration', 'full_audit_summary', 'p2_smoke']
- schema:
  - `axis2`: dict
  - `axis2.axis2`: dict
  - `axis2.axis2.axis`: int
  - `axis2.axis2.details`: dict
  - `axis2.axis2.details.analyzed`: list[dict] len=50
  - `axis2.axis2.details.analyzed[].duplicate_rate`: float
  - `axis2.axis2.details.analyzed[].empty_count`: int
  - `axis2.axis2.details.analyzed[].jsonl_path`: str
  - `axis2.axis2.details.analyzed[].n`: int
  - `axis2.axis2.details.analyzed[].task_id`: str
  - `axis2.axis2.details.analyzed[].truncated_heuristic_count`: int
  - `axis2.axis2.fix_required`: str
  - `axis2.axis2.measurement`: str
  - `axis2.axis2.name`: str
  - `axis2.axis2.verdict`: str
  - `axis2.human_spot_check_for_zach`: dict
  - `axis2.human_spot_check_for_zach.CODE`: list[dict] len=5
  - `axis2.human_spot_check_for_zach.CODE[].candidate_id`: str
  - `axis2.human_spot_check_for_zach.CODE[].content_preview`: str
  - `axis2.human_spot_check_for_zach.CODE[].malformed`: bool
  - `axis2.human_spot_check_for_zach.CODE[].task_id`: str
  - `axis2.human_spot_check_for_zach.CODE[].truncated_suspect`: bool
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING`: list[dict] len=5
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING[].candidate_id`: str
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING[].content_preview`: str
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING[].malformed`: bool
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING[].task_id`: str
  - `axis2.human_spot_check_for_zach.FUNCTION_CALLING[].truncated_suspect`: bool
  - `axis2.human_spot_check_for_zach.MATH`: list[dict] len=5
  - `axis2.human_spot_check_for_zach.MATH[].candidate_id`: str
  - `axis2.human_spot_check_for_zach.MATH[].content_preview`: str
  - `axis2.human_spot_check_for_zach.MATH[].malformed`: bool
  - `axis2.human_spot_check_for_zach.MATH[].task_id`: str
  - `axis2.human_spot_check_for_zach.MATH[].truncated_suspect`: bool
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION`: list[dict] len=5
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION[].candidate_id`: str
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION[].content_preview`: str
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION[].malformed`: bool
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION[].task_id`: str
  - `axis2.human_spot_check_for_zach.STRUCTURED_EXTRACTION[].truncated_suspect`: bool
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL`: list[dict] len=5
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL[].candidate_id`: str
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL[].content_preview`: str
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL[].malformed`: bool
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL[].task_id`: str
  - `axis2.human_spot_check_for_zach.TEXT_TO_SQL[].truncated_suspect`: bool
  - `axis2.human_spot_check_note`: str
  - `calibration`: dict
  - `calibration.d5_scaling_count`: int
  - `calibration.domains_below_20_scaling`: list[empty] len=0
  - `calibration.oracle_spot_verify`: dict
  - `calibration.oracle_spot_verify.CODE`: dict
  - `calibration.oracle_spot_verify.CODE.checked`: int
  - `calibration.oracle_spot_verify.CODE.oracle_verifier_mismatches`: int
  - `calibration.oracle_spot_verify.CODE.task_id`: str
  - `calibration.oracle_spot_verify.FUNCTION_CALLING`: dict
  - `calibration.oracle_spot_verify.FUNCTION_CALLING.checked`: int
  - `calibration.oracle_spot_verify.FUNCTION_CALLING.oracle_verifier_mismatches`: int
  - `calibration.oracle_spot_verify.FUNCTION_CALLING.task_id`: str
  - `calibration.oracle_spot_verify.MATH`: dict
  - `calibration.oracle_spot_verify.MATH.checked`: int
  - `calibration.oracle_spot_verify.MATH.oracle_verifier_mismatches`: int
  - `calibration.oracle_spot_verify.MATH.task_id`: str
  - `calibration.oracle_spot_verify.STRUCTURED_EXTRACTION`: dict
  - `calibration.oracle_spot_verify.STRUCTURED_EXTRACTION.checked`: int
  - `calibration.oracle_spot_verify.STRUCTURED_EXTRACTION.oracle_verifier_mismatches`: int
  - `calibration.oracle_spot_verify.STRUCTURED_EXTRACTION.task_id`: str
  - `calibration.oracle_spot_verify.TEXT_TO_SQL`: dict
  - `calibration.oracle_spot_verify.TEXT_TO_SQL.checked`: int
  - `calibration.oracle_spot_verify.TEXT_TO_SQL.oracle_verifier_mismatches`: int
  - `calibration.oracle_spot_verify.TEXT_TO_SQL.task_id`: str
  - `calibration.oracle_spot_verify.pass`: bool
  - `calibration.oracle_spot_verify.total_checked`: int
  - `calibration.oracle_spot_verify.total_mismatches`: int
  - `calibration.path`: str
  - `calibration.per_domain`: dict
  - `calibration.per_domain.CODE`: dict
  - `calibration.per_domain.CODE.SCALING`: int
  - `calibration.per_domain.FUNCTION_CALLING`: dict
  - `calibration.per_domain.FUNCTION_CALLING.SCALING`: int
```json
{
  "axis2": {
    "axis2": {
      "axis": 2,
      "details": {
        "analyzed": [
          {
            "duplicate_rate": 0.13916015625,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-001.jsonl",
            "n": 2048,
            "task_id": "CODE-001",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.13525390625,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-002.jsonl",
            "n": 2048,
            "task_id": "CODE-002",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.12451171875,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-003.jsonl",
            "n": 2048,
            "task_id": "CODE-003",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.12060546875,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-004.jsonl",
            "n": 2048,
            "task_id": "CODE-004",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.1220703125,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-005.jsonl",
            "n": 2048,
            "task_id": "CODE-005",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.13134765625,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-006.jsonl",
            "n": 2048,
            "task_id": "CODE-006",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.1201171875,
            "empty_count": 0,
            "jsonl_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/cap01/pools/frozen/CODE-007.jsonl",
            "n": 2048,
            "task_id": "CODE-007",
            "truncated_heuristic_count": 0
          },
          {
            "duplicate_rate": 0.11328125,
            "empty_count": 0,
            "
```

### `apu_characterization\out\cap01\verification_audit.json` size=39916
- format: JSON
- top keys: ['protocol_version', 'audit', 'g8', 'axes', 'summary', 'p3_eligible', 'p3_blocked_reason']
- schema:
  - `audit`: str
  - `axes`: list[dict] len=7
  - `axes[].axis`: int
  - `axes[].details`: dict
  - `axes[].details.absolute_half_width_ms`: float
  - `axes[].details.domains`: dict
  - `axes[].details.domains.CODE`: dict
  - `axes[].details.domains.CODE.band_median_ms`: float
  - `axes[].details.domains.CODE.errors`: list[empty] len=0
  - `axes[].details.domains.CODE.harnesses`: dict
  - `axes[].details.domains.CODE.iqrs_ms`: dict
  - `axes[].details.domains.CODE.parity_pass`: bool
  - `axes[].details.domains.FUNCTION_CALLING`: dict
  - `axes[].details.domains.FUNCTION_CALLING.band_median_ms`: float
  - `axes[].details.domains.FUNCTION_CALLING.errors`: list[empty] len=0
  - `axes[].details.domains.FUNCTION_CALLING.harnesses`: dict
  - `axes[].details.domains.FUNCTION_CALLING.iqrs_ms`: dict
  - `axes[].details.domains.FUNCTION_CALLING.parity_pass`: bool
  - `axes[].details.domains.MATH`: dict
  - `axes[].details.domains.MATH.band_median_ms`: float
  - `axes[].details.domains.MATH.errors`: list[empty] len=0
  - `axes[].details.domains.MATH.harnesses`: dict
  - `axes[].details.domains.MATH.iqrs_ms`: dict
  - `axes[].details.domains.MATH.parity_pass`: bool
  - `axes[].details.domains.STRUCTURED_EXTRACTION`: dict
  - `axes[].details.domains.STRUCTURED_EXTRACTION.band_median_ms`: float
  - `axes[].details.domains.STRUCTURED_EXTRACTION.errors`: list[empty] len=0
  - `axes[].details.domains.STRUCTURED_EXTRACTION.harnesses`: dict
  - `axes[].details.domains.STRUCTURED_EXTRACTION.iqrs_ms`: dict
  - `axes[].details.domains.STRUCTURED_EXTRACTION.parity_pass`: bool
  - `axes[].details.domains.TEXT_TO_SQL`: dict
  - `axes[].details.domains.TEXT_TO_SQL.band_median_ms`: float
  - `axes[].details.domains.TEXT_TO_SQL.errors`: list[empty] len=0
  - `axes[].details.domains.TEXT_TO_SQL.harnesses`: dict
  - `axes[].details.domains.TEXT_TO_SQL.iqrs_ms`: dict
  - `axes[].details.domains.TEXT_TO_SQL.parity_pass`: bool
  - `axes[].details.failures`: list[empty] len=0
  - `axes[].details.flagged`: list[empty] len=0
  - `axes[].details.gate`: str
  - `axes[].details.measured_pass`: bool
  - `axes[].details.pass`: bool
  - `axes[].details.relative_tolerance`: float
  - `axes[].details.repeats`: int
  - `axes[].fix_required`: NoneType
  - `axes[].measurement`: str
  - `axes[].name`: str
  - `axes[].verdict`: str
  - `g8`: dict
  - `g8.domains`: dict
  - `g8.domains.CODE`: dict
  - `g8.domains.CODE.band_median_ms`: float
  - `g8.domains.CODE.errors`: list[empty] len=0
  - `g8.domains.CODE.harnesses`: dict
  - `g8.domains.CODE.harnesses.langgraph`: dict
  - `g8.domains.CODE.harnesses.raw_python`: dict
  - `g8.domains.CODE.harnesses.rust`: dict
  - `g8.domains.CODE.iqrs_ms`: dict
  - `g8.domains.CODE.iqrs_ms.langgraph`: float
  - `g8.domains.CODE.iqrs_ms.raw_python`: float
  - `g8.domains.CODE.iqrs_ms.rust`: float
  - `g8.domains.CODE.parity_pass`: bool
  - `g8.domains.FUNCTION_CALLING`: dict
  - `g8.domains.FUNCTION_CALLING.band_median_ms`: float
  - `g8.domains.FUNCTION_CALLING.errors`: list[empty] len=0
  - `g8.domains.FUNCTION_CALLING.harnesses`: dict
  - `g8.domains.FUNCTION_CALLING.harnesses.langgraph`: dict
  - `g8.domains.FUNCTION_CALLING.harnesses.raw_python`: dict
  - `g8.domains.FUNCTION_CALLING.harnesses.rust`: dict
  - `g8.domains.FUNCTION_CALLING.iqrs_ms`: dict
  - `g8.domains.FUNCTION_CALLING.iqrs_ms.langgraph`: float
  - `g8.domains.FUNCTION_CALLING.iqrs_ms.raw_python`: float
  - `g8.domains.FUNCTION_CALLING.iqrs_ms.rust`: float
  - `g8.domains.FUNCTION_CALLING.parity_pass`: bool
  - `g8.domains.MATH`: dict
  - `g8.domains.MATH.band_median_ms`: float
  - `g8.domains.MATH.errors`: list[empty] len=0
  - `g8.domains.MATH.harnesses`: dict
  - `g8.domains.MATH.harnesses.langgraph`: dict
  - `g8.domains.MATH.harnesses.raw_python`: dict
  - `g8.domains.MATH.harnesses.rust`: dict
```json
{
  "protocol_version": "cap01_v2",
  "audit": "CAP-01 full behavioral verification",
  "g8": {
    "gate": "G8",
    "name": "verifier_cost_parity",
    "pass": true,
    "primary_eligible": true,
    "errors": [],
    "relative_tolerance": 0.15,
    "domains": {
      "FUNCTION_CALLING": {
        "harnesses": {
          "langgraph": {
            "available": true,
            "n": 200,
            "median_ms": 0.15123599999999998,
            "iqr_ms": 0.04529949999999999,
            "min_ms": 0.12902,
            "max_ms": 3.574642,
            "warmup_discarded": 10
          },
          "rust": {
            "available": true,
            "n": 200,
            "median_ms": 0.2015845,
            "iqr_ms": 0.177671,
            "min_ms": 0.122906,
            "max_ms": 4.620395,
            "warmup_discarded": 10
          },
          "raw_python": {
            "available": true,
            "n": 200,
            "median_ms": 0.0952375,
            "iqr_ms": 0.02076900000000001,
            "min_ms": 0.084384,
            "max_ms": 1.275063,
            "warmup_discarded": 10
          }
        },
        "band_median_ms": 0.15123599999999998,
        "parity_pass": true,
        "errors": [],
        "iqrs_ms": {
          "langgraph": 0.04529949999999999,
          "rust": 0.177671,
          "raw_python": 0.02076900000000001
        }
      },
      "TEXT_TO_SQL": {
        "harnesses": {
          "raw_python": {
            "available": true,
            "n": 200,
            "median_ms": 0.1709645,
            "iqr_ms": 0.05587700000000001,
            "min_ms": 0.139055,
            "max_ms": 2.468294,
            "warmup_discarded": 10
          },
          "rust": {
            "available": true,
            "n": 200,
            "median_ms": 0.39200650000000004,
            "iqr_ms": 0.2609794999999999,
            "min_ms": 0.205282,
            "max_ms": 1.812628,
            "warmup_discarded": 10
          },
          "langgraph": {
            "available": true,
            "n": 200,
            "median_ms": 0.27473499999999995,
            "iqr_ms": 0.184295,
            "min_ms": 0.213968,
            "max_ms": 1.848405,
            "warmup_discarded": 10
          }
        },
        "band_median_ms": 0.27473499999999995,
        "parity_pass": true,
        "errors": [],
        "iqrs_ms": {
          "raw_python": 0.05587700000000001,
          "rust": 0.2609794999999999,
          "langgraph": 0.184295
        }
      },
```

### `apu_characterization\out\cap01\verifier_ground_truth_audit.json` size=78565
- format: JSON
- top keys: ['rows', 'summary', 'tasks']
- schema:
  - `rows`: list[dict] len=250
  - `rows[].domain`: str
  - `rows[].garbage_error`: str
  - `rows[].garbage_fail`: bool
  - `rows[].garbage_status`: str
  - `rows[].gold_build_error`: str
  - `rows[].gold_error`: str
  - `rows[].gold_pass`: bool
  - `rows[].gold_status`: str
  - `rows[].task_id`: str
  - `summary`: dict
  - `summary.CODE`: dict
  - `summary.CODE.garbage_accept`: int
  - `summary.CODE.garbage_fail`: int
  - `summary.CODE.gold_fail`: int
  - `summary.CODE.gold_pass`: int
  - `summary.CODE.healthy`: bool
  - `summary.CODE.n`: int
  - `summary.CODE.sample_garbage_accepts`: list[empty] len=0
  - `summary.CODE.sample_gold_failures`: list[empty] len=0
  - `summary.FUNCTION_CALLING`: dict
  - `summary.FUNCTION_CALLING.garbage_accept`: int
  - `summary.FUNCTION_CALLING.garbage_fail`: int
  - `summary.FUNCTION_CALLING.gold_fail`: int
  - `summary.FUNCTION_CALLING.gold_pass`: int
  - `summary.FUNCTION_CALLING.healthy`: bool
  - `summary.FUNCTION_CALLING.n`: int
  - `summary.FUNCTION_CALLING.sample_garbage_accepts`: list[empty] len=0
  - `summary.FUNCTION_CALLING.sample_gold_failures`: list[empty] len=0
  - `summary.MATH`: dict
  - `summary.MATH.garbage_accept`: int
  - `summary.MATH.garbage_fail`: int
  - `summary.MATH.gold_fail`: int
  - `summary.MATH.gold_pass`: int
  - `summary.MATH.healthy`: bool
  - `summary.MATH.n`: int
  - `summary.MATH.sample_garbage_accepts`: list[empty] len=0
  - `summary.MATH.sample_gold_failures`: list[dict] len=1
  - `summary.MATH.sample_gold_failures[].error`: str
  - `summary.MATH.sample_gold_failures[].status`: str
  - `summary.MATH.sample_gold_failures[].task_id`: str
  - `summary.STRUCTURED_EXTRACTION`: dict
  - `summary.STRUCTURED_EXTRACTION.garbage_accept`: int
  - `summary.STRUCTURED_EXTRACTION.garbage_fail`: int
  - `summary.STRUCTURED_EXTRACTION.gold_fail`: int
  - `summary.STRUCTURED_EXTRACTION.gold_pass`: int
  - `summary.STRUCTURED_EXTRACTION.healthy`: bool
  - `summary.STRUCTURED_EXTRACTION.n`: int
  - `summary.STRUCTURED_EXTRACTION.sample_garbage_accepts`: list[empty] len=0
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures`: list[dict] len=5
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].error`: str
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].status`: str
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].task_id`: str
  - `summary.TEXT_TO_SQL`: dict
  - `summary.TEXT_TO_SQL.garbage_accept`: int
  - `summary.TEXT_TO_SQL.garbage_fail`: int
  - `summary.TEXT_TO_SQL.gold_fail`: int
  - `summary.TEXT_TO_SQL.gold_pass`: int
  - `summary.TEXT_TO_SQL.healthy`: bool
  - `summary.TEXT_TO_SQL.n`: int
  - `summary.TEXT_TO_SQL.sample_garbage_accepts`: list[empty] len=0
  - `summary.TEXT_TO_SQL.sample_gold_failures`: list[dict] len=1
  - `summary.TEXT_TO_SQL.sample_gold_failures[].error`: str
  - `summary.TEXT_TO_SQL.sample_gold_failures[].status`: str
  - `summary.TEXT_TO_SQL.sample_gold_failures[].task_id`: str
  - `tasks`: int
```json
{
  "rows": [
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-001"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-002"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-003"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-004"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-005"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-006"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-007"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-008"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": true,
      "gold_status": "pass",
      "task_id": "CODE-009"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_e
```

### `apu_characterization\out\cap01\verifier_ground_truth_audit_wsl.json` size=81531
- format: JSON
- top keys: ['rows', 'summary', 'tasks']
- schema:
  - `rows`: list[dict] len=250
  - `rows[].domain`: str
  - `rows[].garbage_error`: str
  - `rows[].garbage_fail`: bool
  - `rows[].garbage_status`: str
  - `rows[].gold_build_error`: str
  - `rows[].gold_error`: str
  - `rows[].gold_pass`: bool
  - `rows[].gold_status`: str
  - `rows[].task_id`: str
  - `summary`: dict
  - `summary.CODE`: dict
  - `summary.CODE.garbage_accept`: int
  - `summary.CODE.garbage_fail`: int
  - `summary.CODE.gold_fail`: int
  - `summary.CODE.gold_pass`: int
  - `summary.CODE.healthy`: bool
  - `summary.CODE.n`: int
  - `summary.CODE.sample_garbage_accepts`: list[empty] len=0
  - `summary.CODE.sample_gold_failures`: list[dict] len=5
  - `summary.CODE.sample_gold_failures[].error`: str
  - `summary.CODE.sample_gold_failures[].status`: str
  - `summary.CODE.sample_gold_failures[].task_id`: str
  - `summary.FUNCTION_CALLING`: dict
  - `summary.FUNCTION_CALLING.garbage_accept`: int
  - `summary.FUNCTION_CALLING.garbage_fail`: int
  - `summary.FUNCTION_CALLING.gold_fail`: int
  - `summary.FUNCTION_CALLING.gold_pass`: int
  - `summary.FUNCTION_CALLING.healthy`: bool
  - `summary.FUNCTION_CALLING.n`: int
  - `summary.FUNCTION_CALLING.sample_garbage_accepts`: list[empty] len=0
  - `summary.FUNCTION_CALLING.sample_gold_failures`: list[dict] len=5
  - `summary.FUNCTION_CALLING.sample_gold_failures[].error`: str
  - `summary.FUNCTION_CALLING.sample_gold_failures[].status`: str
  - `summary.FUNCTION_CALLING.sample_gold_failures[].task_id`: str
  - `summary.MATH`: dict
  - `summary.MATH.garbage_accept`: int
  - `summary.MATH.garbage_fail`: int
  - `summary.MATH.gold_fail`: int
  - `summary.MATH.gold_pass`: int
  - `summary.MATH.healthy`: bool
  - `summary.MATH.n`: int
  - `summary.MATH.sample_garbage_accepts`: list[empty] len=0
  - `summary.MATH.sample_gold_failures`: list[dict] len=1
  - `summary.MATH.sample_gold_failures[].error`: str
  - `summary.MATH.sample_gold_failures[].status`: str
  - `summary.MATH.sample_gold_failures[].task_id`: str
  - `summary.STRUCTURED_EXTRACTION`: dict
  - `summary.STRUCTURED_EXTRACTION.garbage_accept`: int
  - `summary.STRUCTURED_EXTRACTION.garbage_fail`: int
  - `summary.STRUCTURED_EXTRACTION.gold_fail`: int
  - `summary.STRUCTURED_EXTRACTION.gold_pass`: int
  - `summary.STRUCTURED_EXTRACTION.healthy`: bool
  - `summary.STRUCTURED_EXTRACTION.n`: int
  - `summary.STRUCTURED_EXTRACTION.sample_garbage_accepts`: list[empty] len=0
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures`: list[dict] len=5
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].error`: str
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].status`: str
  - `summary.STRUCTURED_EXTRACTION.sample_gold_failures[].task_id`: str
  - `summary.TEXT_TO_SQL`: dict
  - `summary.TEXT_TO_SQL.garbage_accept`: int
  - `summary.TEXT_TO_SQL.garbage_fail`: int
  - `summary.TEXT_TO_SQL.gold_fail`: int
  - `summary.TEXT_TO_SQL.gold_pass`: int
  - `summary.TEXT_TO_SQL.healthy`: bool
  - `summary.TEXT_TO_SQL.n`: int
  - `summary.TEXT_TO_SQL.sample_garbage_accepts`: list[empty] len=0
  - `summary.TEXT_TO_SQL.sample_gold_failures`: list[dict] len=5
  - `summary.TEXT_TO_SQL.sample_gold_failures[].error`: str
  - `summary.TEXT_TO_SQL.sample_gold_failures[].status`: str
  - `summary.TEXT_TO_SQL.sample_gold_failures[].task_id`: str
  - `tasks`: int
```json
{
  "rows": [
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-001"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-002"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-003"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-004"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-005"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-006"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-007"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-008"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
      "gold_build_error": "",
      "gold_error": "",
      "gold_pass": false,
      "gold_status": "wrong",
      "task_id": "CODE-009"
    },
    {
      "domain": "CODE",
      "garbage_error": "",
      "garbage_fail": true,
      "garbage_status": "wrong",
 
```

### `apu_characterization\out\cap01\verifier_pin_manifest.json` size=1818
- format: JSON
- top keys: ['adapters', 'bfcl', 'code_sandbox', 'cpython', 'jsonschema', 'sqlite']
- schema:
  - `adapters`: dict
  - `adapters.note`: str
  - `adapters.sha256`: dict
  - `adapters.sha256.bfcl_cap01_checker.py`: str
  - `adapters.sha256.bfcl_shims/__init__.py`: str
  - `adapters.sha256.bfcl_shims/java_parser.py`: str
  - `adapters.sha256.bfcl_shims/js_parser.py`: str
  - `adapters.sha256.domain_verifiers.py`: str
  - `adapters.sha256.verifier.py`: str
  - `bfcl`: dict
  - `bfcl.adoption`: str
  - `bfcl.corpus_test_category`: str
  - `bfcl.source_sha256`: str
  - `bfcl.tree_sitter_policy`: dict
  - `bfcl.tree_sitter_policy.cap01_runtime`: str
  - `bfcl.tree_sitter_policy.upstream_metadata_pins`: dict
  - `bfcl.tree_sitter_policy.upstream_metadata_pins.tree_sitter`: str
  - `bfcl.tree_sitter_policy.upstream_metadata_pins.tree_sitter_java`: str
  - `bfcl.tree_sitter_policy.upstream_metadata_pins.tree_sitter_javascript`: str
  - `bfcl.version`: str
  - `code_sandbox`: dict
  - `code_sandbox.note`: str
  - `code_sandbox.python_flags`: list[str] len=1
  - `code_sandbox.wall_seconds_default`: int
  - `cpython`: dict
  - `cpython.version`: str
  - `jsonschema`: dict
  - `jsonschema.version`: str
  - `sqlite`: dict
  - `sqlite.version`: str
```json
{
  "adapters": {
    "note": "Scoring-relevant adapter layer previously outside the BFCL wrapper pin; covered after died-ledger #11 coverage-hole fix.",
    "sha256": {
      "bfcl_cap01_checker.py": "2457082b6b0e9981546897192e4eabc4daeaf5109e86185b25fc6973fa85f4f5",
      "bfcl_shims/__init__.py": "b0efe89d9fc02f85f40479088d21ecbb1b964e108a9b5c2383acf1238fcb8879",
      "bfcl_shims/java_parser.py": "63620bcdca4ec5b51f105ef59f8f0b3f841709c3d5739404f222528754ec8575",
      "bfcl_shims/js_parser.py": "08e77968b612c9926bd4689076fef7ef94cde348de450598d6c47cb96ca9ecc9",
      "domain_verifiers.py": "2698c6797efe136903ed1de5a1b92c1d6aaa7d334e9c74596f9e66a42364fbea",
      "verifier.py": "46826bd94e81f3e3292742dd88f0bba833823b3244ff15cce497c7178288e605"
    }
  },
  "bfcl": {
    "adoption": "bfcl_eval.ast_checker via cap01 wrapper",
    "corpus_test_category": "live_multiple_python_only",
    "source_sha256": "2457082b6b0e9981546897192e4eabc4daeaf5109e86185b25fc6973fa85f4f5",
    "tree_sitter_policy": {
      "cap01_runtime": "Java/JS parsers stubbed via bfcl_shims so Python-only live_multiple scoring does not require compiling tree_sitter==0.21.3 on hosts without matching wheels (died-ledger #11).",
      "upstream_metadata_pins": {
        "tree_sitter": "0.21.3",
        "tree_sitter_java": "0.21.0",
        "tree_sitter_javascript": "0.21.4"
      }
    },
    "version": "v4"
  },
  "code_sandbox": {
    "note": "Dropped -S so HumanEval+ numpy imports work; runner invokes check(entry_point); network blocked in-process (died-ledger #11).",
    "python_flags": [
      "-B"
    ],
    "wall_seconds_default": 30
  },
  "cpython": {
    "version": "3.14.0"
  },
  "jsonschema": {
    "version": "4.26.0"
  },
  "sqlite": {
    "version": "3.50.4"
  }
}
```

### BFCL multi_turn datasets under CAP-01: 10
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_base.json` parse error Extra data: line 2 column 1 (char 1985)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_long_context.json` parse error Extra data: line 2 column 1 (char 1993)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_func.json` parse error Extra data: line 2 column 1 (char 2030)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_param.json` parse error Extra data: line 2 column 1 (char 2181)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_base.json` parse error Extra data: line 2 column 1 (char 438)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_long_context.json` parse error Extra data: line 2 column 1 (char 446)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_func.json` parse error Extra data: line 2 column 1 (char 447)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_param.json` parse error Extra data: line 2 column 1 (char 448)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\possible_answer\BFCL_v4_multi_turn_composite.json` parse error Extra data: line 2 column 1 (char 451)
- `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\question\BFCL_v4_multi_turn_composite.json` parse error Extra data: line 2 column 1 (char 1714)


## 4. TLP-01

Exists: True
- dependence_graphs_v2 Tier_0.json count: 50
- candidate files (sample up to 60): 8

### `apu_characterization\out\tlp01\_gate_smoke\aggregate.json` size=29873
- JSON object keys=['validity_class', 'protocol_version', 'data_source', 'headline_form', 'replication_floor', 'm1a_speedup_bands', 'm1b_speedup_bands', 'm2_speedup_bands', 'm3_speedup_bands', 'floor_tax_m2_minus_m1b', 'speculation_headroom', 'sparse_descriptive', 'ceiling_claim', 'claim', 'blocked_claims', 'ownable_firsts', 'session_count', 'banded_session_count', 'phase_diagram', 'frontier_claim', 'bystander_contention', 'm5_at_optimal_policy', 'result_validity']
  - `banded_session_count`: int
  - `blocked_claims`: list[str] len=15
  - `bystander_contention`: dict
  - `bystander_contention.method`: str
  - `bystander_contention.per_policy`: dict
  - `bystander_contention.per_policy.always_top1`: dict
  - `bystander_contention.per_policy.always_top1.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.always_top1.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.always_top1.median_primary_slowdown`: float
  - `bystander_contention.per_policy.always_top1.n`: int
  - `bystander_contention.per_policy.breadth_2`: dict
  - `bystander_contention.per_policy.breadth_2.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_2.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_2.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_2.n`: int
  - `bystander_contention.per_policy.breadth_3`: dict
  - `bystander_contention.per_policy.breadth_3.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_3.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_3.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_3.n`: int
  - `bystander_contention.per_policy.breadth_5`: dict
  - `bystander_contention.per_policy.breadth_5.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_5.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_5.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_5.n`: int
  - `bystander_contention.per_policy.confidence_gated`: dict
  - `bystander_contention.per_policy.confidence_gated.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.confidence_gated.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.confidence_gated.median_primary_slowdown`: float
  - `bystander_contention.per_policy.confidence_gated.n`: int
  - `bystander_contention.scope`: str
  - `bystander_contention.secondary`: bool
  - `ceiling_claim`: dict
  - `ceiling_claim.criterion`: str
  - `ceiling_claim.data_source`: str
  - `ceiling_claim.language`: str
  - `ceiling_claim.multi_tool_tier_c_m1_bands`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.FO`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.FO.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.FO.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.FO.min`: float
  - `ceiling_claim.name`: str
  - `ceiling_claim.rung`: NoneType
  - `ceiling_claim.smoke_diagnostic`: str
  - `ceiling_claim.track`: str
  - `claim`: dict
  - `claim.criterion`: str
  - `claim.data_source`: str
  - `claim.language`: str
  - `claim.multi_tool_tier_c_m1_bands`: dict
  - `claim.multi_tool_tier_c_m1_bands.FO`: dict
  - `claim.multi_tool_tier_c_m1_bands.FO.max`: float
  - `claim.multi_tool_tier_c_m1_bands.FO.median`: float
  - `claim.multi_tool_tier_c_m1_bands.FO.min`: float
  - `claim.name`: str
  - `claim.rung`: NoneType
  - `claim.smoke_diagnostic`: str
  - `claim.track`: str
  - `data_source`: str
  - `floor_tax_m2_minus_m1b`: dict
  - `floor_tax_m2_minus_m1b.CN`: dict
  - `floor_tax_m2_minus_m1b.CN.Tier_C`: float
  - `floor_tax_m2_minus_m1b.CN.Tier_S`: float
  - `floor_tax_m2_minus_m1b.FO`: dict
  - `floor_tax_m2_minus_m1b.FO.Tier_C`: float
  - `floor_tax_m2_minus_m1b.FO.Tier_S`: float
  - `frontier_claim`: dict
  - `frontier_claim.boundary_exists`: bool
  - `frontier_claim.criterion`: str
  - `frontier_claim.data_source`: str
  - `frontier_claim.language`: str
  - `frontier_claim.name`: str
  - `frontier_claim.praetor_aggressive`: bool
  - `frontier_claim.praetor_label`: str
  - `frontier_claim.rung`: NoneType
  - `frontier_claim.smoke_diagnostic`: str
  - `frontier_claim.track`: str
  - `headline_form`: str
  - `m1a_speedup_bands`: dict
  - `m1a_speedup_bands.CN`: dict
```json
{
  "validity_class": "turn_level_parallelism",
  "protocol_version": "tlp01_v2.1",
  "data_source": "synthetic_smoke",
  "headline_form": "S_C_bracket_never_point",
  "replication_floor": {
    "required_seeds": 5,
    "behavior": "exclusion_with_separate_section",
    "eligible_task_ids": [
      {
        "task_id": "CN",
        "n": 5,
        "seeds": [
          0,
          1,
          2,
          3,
          4
        ],
        "sources": [
          "SYN"
        ],
        "session_count": 5,
        "disposition": "banded"
      },
      {
        "task_id": "FO",
        "n": 5,
        "seeds": [
          0,
          1,
          2,
          3,
          4
        ],
        "sources": [
          "SYN"
        ],
        "session_count": 5,
        "disposition": "banded"
      }
    ],
    "sparse_task_ids": [],
    "eligible_session_count": 10,
    "sparse_session_count": 0
  },
  "m1a_speedup_bands": {
    "CN": {
      "Tier_C": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      },
      "Tier_S": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      }
    },
    "FO": {
      "Tier_C": {
        "min": 2.0,
        "median": 2.0,
        "max": 2.0
      },
      "Tier_S": {
        "min": 2.0,
        "median": 2.0,
        "max": 2.0
      }
    }
  },
  "m1b_speedup_bands": {
    "CN": {
      "Tier_C": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      },
      "Tier_S": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      }
    },
    "FO": {
      "Tier_C": {
        "min": 3.0,
        "median": 3.0,
        "max": 3.0
      },
      "Tier_S": {
        "min": 3.0,
        "median": 3.0,
        "max": 3.0
      }
    }
  },
  "m2_speedup_bands": {
    "CN": {
      "Tier_C": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      },
      "Tier_S": {
        "min": 1.0,
        "median": 1.0,
        "max": 1.0
      }
    },
    "FO": {
      "Tier_C": {
        "min": 3.0,
        "median": 3.0,
        "max": 3.0
      },
      "Tier_S": {
        "min": 3.0,
        "median": 3.0,
        "max": 3.0
      }
    }
  },
  "m3_speedup_bands": {
    "2": {
      "CN": {
        "Tier_C": {
          "min": 1.0,
          "median": 1.0,
          "max": 1.0
        },
        "Tier_S": {
          "min": 1.0,
          "median": 1.0,
          "max": 1.0
        }
      },
      "FO": {
        "Tier_C": {
          "min": 1.5,
          "
```

### `apu_characterization\out\tlp01\dependence_graphs\t1_graph_report.md` size=1071

### `apu_characterization\out\tlp01\dependence_graphs_v2\t1_graph_report.md` size=1071

### `apu_characterization\out\tlp01\t2\aggregate.json` size=1921688
- JSON object keys=['aggregate_sha256', 'banded_session_count', 'blocked_claims', 'bystander_contention', 'ceiling_claim', 'claim', 'data_source', 'floor_tax_m2_minus_m1b', 'frontier_claim', 'headline_form', 'm0_g_v', 'm1a_speedup_bands', 'm1a_speedup_bands_by_source', 'm1b_speedup_bands', 'm1b_speedup_bands_by_source', 'm2_speedup_bands', 'm2_speedup_bands_by_source', 'm3_speedup_bands', 'm5_at_optimal_policy', 'ownable_firsts', 'phase_diagram', 'protocol_version', 'replication_floor', 'session_count', 'sparse_descriptive', 'speculation_headroom', 't1_index_sha256', 'validity_class']
  - `aggregate_sha256`: str
  - `banded_session_count`: int
  - `blocked_claims`: list[str] len=11
  - `bystander_contention`: dict
  - `bystander_contention.method`: str
  - `bystander_contention.per_policy`: dict
  - `bystander_contention.per_policy.always_top1`: dict
  - `bystander_contention.per_policy.always_top1.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.always_top1.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.always_top1.median_primary_slowdown`: float
  - `bystander_contention.per_policy.always_top1.n`: int
  - `bystander_contention.per_policy.breadth_2`: dict
  - `bystander_contention.per_policy.breadth_2.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_2.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_2.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_2.n`: int
  - `bystander_contention.per_policy.breadth_3`: dict
  - `bystander_contention.per_policy.breadth_3.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_3.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_3.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_3.n`: int
  - `bystander_contention.per_policy.breadth_5`: dict
  - `bystander_contention.per_policy.breadth_5.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.breadth_5.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_5.median_primary_slowdown`: float
  - `bystander_contention.per_policy.breadth_5.n`: int
  - `bystander_contention.per_policy.confidence_gated`: dict
  - `bystander_contention.per_policy.confidence_gated.contention_tax_per_inflight`: float
  - `bystander_contention.per_policy.confidence_gated.mean_primary_slowdown`: float
  - `bystander_contention.per_policy.confidence_gated.median_primary_slowdown`: float
  - `bystander_contention.per_policy.confidence_gated.n`: int
  - `bystander_contention.scope`: str
  - `bystander_contention.secondary`: bool
  - `ceiling_claim`: dict
  - `ceiling_claim.criterion`: str
  - `ceiling_claim.data_source`: str
  - `ceiling_claim.language`: str
  - `ceiling_claim.multi_tool_tier_c_m1_bands`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-02`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-02.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-02.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.LH-02.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-02`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-02.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-02.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-CMP-02.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FAN-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FAN-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FAN-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FAN-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FILE-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FILE-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FILE-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-FILE-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-02`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-02.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-02.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-MIX-02.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-01.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-01.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-01.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-02`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-02.max`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-02.median`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-RS-02.min`: float
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-SER-01`: dict
  - `ceiling_claim.multi_tool_tier_c_m1_bands.MT-SER-01.max`: float
```json
{
  "aggregate_sha256": "f8ec73f3ff4b9c09d99f57734a9351f3e51346785a4812ddaa9c00c2be6ae36d",
  "banded_session_count": 80,
  "blocked_claims": [
    "Never quote a TLP point estimate \u2014 always the S/C bracket with tier named.",
    "Never quote an unqualified M1 \u2014 always M1a (width, no speculation) or M1b (perfect control speculation).",
    "Never present M1a/M1b oracle numbers as achievable; M4/M5 are the deployable claims.",
    "Never quote speculation headroom as a claim rung until it has pre-registered criteria.",
    "Never quote SER-02's pre-taxonomy 1.72x as a finding \u2014 superseded by v2 M1b under classified SC-EMIT semantics.",
    "Never let Tier-J (LLM-judged) edges into a headline number.",
    "Never generalize beyond the traced task classes and harnesses; S3 absence (if absent) is a stated limit.",
    "Never claim pioneering priority for parallel agent execution \u2014 false per PASTE/B-PASTE/SPORK/LLMCompiler/GAP.",
    "Phase-boundary location is never Tier-D-dependent; only Praetor's position on the penalty axis is Tier D, labeled every occurrence.",
    "The Praetor 20us penalty uses Tier-D constants \u2014 labeled every time; promotion path csynth.",
    "'First agent microarchitecture' is positioning only; it never appears in a results section."
  ],
  "bystander_contention": {
    "method": "observer_effect_primary_path_slowdown_vs_inflight_speculation",
    "per_policy": {
      "always_top1": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.14114534299947426,
        "median_primary_slowdown": 0.07999999929238162,
        "n": 14
      },
      "breadth_2": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.21805555657645884,
        "median_primary_slowdown": 0.133333333144003,
        "n": 14
      },
      "breadth_3": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.28224353606088004,
        "median_primary_slowdown": 0.1999999999453935,
        "n": 14
      },
      "breadth_5": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.3259125435221713,
        "median_primary_slowdown": 0.27123912864764294,
        "n": 14
      },
      "confidence_gated": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.08231277994476026,
        "median_primary_slowdown": 0.005133298016578046,
        "n": 14
      }
    },
    "scope": "software_side_policies",
    "seconda
```

### `apu_characterization\out\tlp01\t2\partition.json` size=5726
- JSON object keys=['behavior', 'eligible_task_ids', 'required_seeds', 'sparse_task_ids']
  - `behavior`: str
  - `eligible_task_ids`: list[dict] len=16
  - `eligible_task_ids[].disposition`: str
  - `eligible_task_ids[].n`: int
  - `eligible_task_ids[].seeds`: list[int] len=5
  - `eligible_task_ids[].session_count`: int
  - `eligible_task_ids[].sources`: list[str] len=1
  - `eligible_task_ids[].task_id`: str
  - `required_seeds`: int
  - `sparse_task_ids`: list[dict] len=8
  - `sparse_task_ids[].disposition`: str
  - `sparse_task_ids[].n`: int
  - `sparse_task_ids[].seeds`: list[int] len=3
  - `sparse_task_ids[].session_count`: int
  - `sparse_task_ids[].sources`: list[str] len=1
  - `sparse_task_ids[].task_id`: str
```json
{
  "behavior": "exclusion_with_separate_section",
  "eligible_task_ids": [
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S1"
      ],
      "task_id": "LH-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S1"
      ],
      "task_id": "LH-02"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-CMP-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-CMP-02"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-FAN-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-FILE-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-MIX-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-MIX-02"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-RS-01"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
        2,
        3,
        4
      ],
      "session_count": 5,
      "sources": [
        "S2"
      ],
      "task_id": "MT-RS-02"
    },
    {
      "disposition": "banded",
      "n": 5,
      "seeds": [
        0,
        1,
   
```

### `apu_characterization\out\tlp01\t2\quotable_extracts.json` size=21040
- JSON object keys=['aggregate_sha', 'bystander', 'canonical_rung_1b', 'canonical_rung_3a', 'ceiling_rung', 'composite_sentence', 'floor_tax_m2_minus_m1b', 'frontier', 'frontier_rung', 'graph_input_sha', 'm1a_bands', 'm1b_bands', 'speculation_headroom']
  - `aggregate_sha`: str
  - `bystander`: dict
  - `bystander.effect`: str
  - `bystander.per_policy`: dict
  - `bystander.per_policy.always_top1`: dict
  - `bystander.per_policy.always_top1.contention_tax_per_inflight`: float
  - `bystander.per_policy.always_top1.mean_primary_slowdown`: float
  - `bystander.per_policy.always_top1.median_primary_slowdown`: float
  - `bystander.per_policy.always_top1.n`: int
  - `bystander.per_policy.breadth_2`: dict
  - `bystander.per_policy.breadth_2.contention_tax_per_inflight`: float
  - `bystander.per_policy.breadth_2.mean_primary_slowdown`: float
  - `bystander.per_policy.breadth_2.median_primary_slowdown`: float
  - `bystander.per_policy.breadth_2.n`: int
  - `bystander.per_policy.breadth_3`: dict
  - `bystander.per_policy.breadth_3.contention_tax_per_inflight`: float
  - `bystander.per_policy.breadth_3.mean_primary_slowdown`: float
  - `bystander.per_policy.breadth_3.median_primary_slowdown`: float
  - `bystander.per_policy.breadth_3.n`: int
  - `bystander.per_policy.breadth_5`: dict
  - `bystander.per_policy.breadth_5.contention_tax_per_inflight`: float
  - `bystander.per_policy.breadth_5.mean_primary_slowdown`: float
  - `bystander.per_policy.breadth_5.median_primary_slowdown`: float
  - `bystander.per_policy.breadth_5.n`: int
  - `bystander.per_policy.confidence_gated`: dict
  - `bystander.per_policy.confidence_gated.contention_tax_per_inflight`: float
  - `bystander.per_policy.confidence_gated.mean_primary_slowdown`: float
  - `bystander.per_policy.confidence_gated.median_primary_slowdown`: float
  - `bystander.per_policy.confidence_gated.n`: int
  - `bystander.ran`: bool
  - `bystander.scope`: str
  - `canonical_rung_1b`: str
  - `canonical_rung_3a`: str
  - `ceiling_rung`: str
  - `composite_sentence`: str
  - `floor_tax_m2_minus_m1b`: dict
  - `floor_tax_m2_minus_m1b.LH-01`: dict
  - `floor_tax_m2_minus_m1b.LH-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.LH-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.LH-02`: dict
  - `floor_tax_m2_minus_m1b.LH-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.LH-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-CMP-01`: dict
  - `floor_tax_m2_minus_m1b.MT-CMP-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-CMP-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-CMP-02`: dict
  - `floor_tax_m2_minus_m1b.MT-CMP-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-CMP-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-FAN-01`: dict
  - `floor_tax_m2_minus_m1b.MT-FAN-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-FAN-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-FILE-01`: dict
  - `floor_tax_m2_minus_m1b.MT-FILE-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-FILE-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-MIX-01`: dict
  - `floor_tax_m2_minus_m1b.MT-MIX-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-MIX-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-MIX-02`: dict
  - `floor_tax_m2_minus_m1b.MT-MIX-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-MIX-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-RS-01`: dict
  - `floor_tax_m2_minus_m1b.MT-RS-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-RS-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-RS-02`: dict
  - `floor_tax_m2_minus_m1b.MT-RS-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-RS-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-SER-01`: dict
  - `floor_tax_m2_minus_m1b.MT-SER-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-SER-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.MT-SER-02`: dict
  - `floor_tax_m2_minus_m1b.MT-SER-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.MT-SER-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.RE-01`: dict
  - `floor_tax_m2_minus_m1b.RE-01.Tier_C`: float
  - `floor_tax_m2_minus_m1b.RE-01.Tier_S`: float
  - `floor_tax_m2_minus_m1b.RE-02`: dict
  - `floor_tax_m2_minus_m1b.RE-02.Tier_C`: float
  - `floor_tax_m2_minus_m1b.RE-02.Tier_S`: float
  - `floor_tax_m2_minus_m1b.RH-01`: dict
  - `floor_tax_m2_minus_m1b.RH-01.Tier_C`: float
```json
{
  "aggregate_sha": "f8ec73f3ff4b9c09d99f57734a9351f3e51346785a4812ddaa9c00c2be6ae36d",
  "bystander": {
    "effect": "Measurable primary-path slowdown under speculation policies; phase diagram uses nominal penalties (conservative for claim).",
    "per_policy": {
      "always_top1": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.14114534299947426,
        "median_primary_slowdown": 0.07999999929238162,
        "n": 14
      },
      "breadth_2": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.21805555657645884,
        "median_primary_slowdown": 0.133333333144003,
        "n": 14
      },
      "breadth_3": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.28224353606088004,
        "median_primary_slowdown": 0.1999999999453935,
        "n": 14
      },
      "breadth_5": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.3259125435221713,
        "median_primary_slowdown": 0.27123912864764294,
        "n": 14
      },
      "confidence_gated": {
        "contention_tax_per_inflight": 0.08,
        "mean_primary_slowdown": 0.08231277994476026,
        "median_primary_slowdown": 0.005133298016578046,
        "n": 14
      }
    },
    "ran": true,
    "scope": "software_side_policies"
  },
  "canonical_rung_1b": "A phase boundary exists in speculation economics, measured from real traces as a function of misprediction penalty: above it, confidence-gated conservative speculation is provably optimal (the PASTE-class regime); below it, aggressive breadth-K speculation dominates. The boundary sits at [5000000, 10000000] ns (per class); a Praetor-class penalty (~20 \u00b5s, Tier D, promotion path csynth) sits 250.0\u00d7 inside the aggressive region.",
  "canonical_rung_3a": "Under a perfect non-speculative scheduler (M1a), the conservative dependence floor (Tier-C) finds agent turn-level work broadly near-serial (~1\u00d7) across this task suite \u2014 including templates designed to contain independent work. Width is not the available lever; the bracket's upper edge (Tier-S) is where remaining headroom lives, and that headroom is speculative, not width-based.",
  "ceiling_rung": "rung_3a",
  "composite_sentence": "Agent workloads are near-serial to any scheduler that doesn't bet; betting has a measured economic boundary; software sits on the wrong side of it and Praetor-class silicon sits on the right side. The only way to par
```

### `apu_characterization\out\tlp01\t2\ser02_s0_chain_dump.md` size=1747

### `apu_characterization\out\tlp01\traces\S1_extract_inventory.json` size=543
- JSON object keys=['by_task', 'discarded', 'limitation', 'source', 'source_artifact', 'usable_traces']
  - `by_task`: dict
  - `by_task.CH-01`: int
  - `by_task.CH-02`: int
  - `by_task.CN-01`: int
  - `by_task.FO-01`: int
  - `by_task.LH-01`: int
  - `by_task.LH-02`: int
  - `by_task.RE-01`: int
  - `by_task.RE-02`: int
  - `by_task.RH-01`: int
  - `by_task.RH-02`: int
  - `by_task.SH-01`: int
  - `by_task.SH-02`: int
  - `by_task.SO-01`: int
  - `by_task.SW-01`: int
  - `discarded`: list[empty] len=0
  - `limitation`: str
  - `source`: str
  - `source_artifact`: str
  - `usable_traces`: int
```json
{
  "by_task": {
    "CH-01": 3,
    "CH-02": 4,
    "CN-01": 3,
    "FO-01": 4,
    "LH-01": 5,
    "LH-02": 5,
    "RE-01": 5,
    "RE-02": 5,
    "RH-01": 5,
    "RH-02": 5,
    "SH-01": 1,
    "SH-02": 2,
    "SO-01": 1,
    "SW-01": 2
  },
  "discarded": [],
  "limitation": "S1 anchors the SERIAL end of the task spectrum; not the basis for the ceiling claim (S2 is).",
  "source": "S1",
  "source_artifact": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/replication_remote_search_v3.json",
  "usable_traces": 50
}
```


## 5. MCP-01 / mcp_tax

Exists: True
- COMPLETE.json count (sampled listing): showing 20 of many
- client/result.json sample: 10

### `apu_characterization\out\mcp_tax\fixphase_resmoke_v10\runs\http_sse_tls_off\t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-full\0\COMPLETE.json`
- keys: ['cell_id', 'cell_plan_sha256', 'complete', 'files', 'layout_version', 'protocol_version', 'seed']
  - `cell_id`: str
  - `cell_plan_sha256`: str
  - `complete`: bool
  - `files`: dict
  - `files.client/result.json`: str
  - `files.gap_overlaps/5.json`: str
  - `files.manifest.json`: str
  - `files.plan.json`: str
  - `files.server/result.json`: str
  - `files.server/stderr.log`: str
  - `files.server/stdout.log`: str
  - `files.server_config.json`: str
  - `files.wire/10_request_0.bin`: str
  - `files.wire/10_response_1.bin`: str
  - `files.wire/11_request_0.bin`: str
  - `files.wire/11_response_1.bin`: str
  - `files.wire/12_request_0.bin`: str
  - `files.wire/12_response_1.bin`: str
  - `files.wire/13_request_0.bin`: str
  - `files.wire/13_response_1.bin`: str
  - `files.wire/14_request_0.bin`: str
  - `files.wire/14_response_1.bin`: str
  - `files.wire/15_request_0.bin`: str
  - `files.wire/15_response_1.bin`: str
  - `files.wire/16_request_0.bin`: str
  - `files.wire/16_response_1.bin`: str
  - `files.wire/17_request_0.bin`: str
  - `files.wire/17_response_1.bin`: str
  - `files.wire/18_request_0.bin`: str
  - `files.wire/18_response_1.bin`: str
  - `files.wire/19_request_0.bin`: str
  - `files.wire/19_response_1.bin`: str
  - `files.wire/1_request_0.bin`: str
  - `files.wire/1_response_1.bin`: str
  - `files.wire/20_request_0.bin`: str
  - `files.wire/20_response_1.bin`: str
  - `files.wire/2_request_0.bin`: str
  - `files.wire/2_response_1.bin`: str
  - `files.wire/3_request_0.bin`: str
  - `files.wire/3_response_1.bin`: str
  - `files.wire/4_request_0.bin`: str
  - `files.wire/4_response_1.bin`: str
  - `files.wire/5_request_0.bin`: str
  - `files.wire/5_response_1.bin`: str
  - `files.wire/6_request_0.bin`: str
  - `files.wire/6_response_1.bin`: str
  - `files.wire/7_request_0.bin`: str
  - `files.wire/7_response_1.bin`: str
  - `files.wire/8_request_0.bin`: str
  - `files.wire/8_response_1.bin`: str
  - `files.wire/9_request_0.bin`: str
  - `files.wire/9_response_1.bin`: str
  - `layout_version`: int
  - `protocol_version`: str
  - `seed`: int
```json
{
  "cell_id": "t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-full",
  "cell_plan_sha256": "ea4246e754897267ef8cf9e8be360a65b81aa9a69f627103ce3817ce630c0a96",
  "complete": true,
  "files": {
    "client/result.json": "272be43cc686b74d7fca77f945956b2b3a8476d02212d9607085dd3ecdf4d735",
    "gap_overlaps/5.json": "92f58d1a5d0cfb11a18ec4193a44e074441c6a1371568a848536e62dd8bc366c",
    "manifest.json": "fc51d8cee1823b09d4fda4d8495241ac1839549febf1618649b7fc14d0214a90",
    "plan.json": "e4b5eb86b810003e119111e373732a4eb0964413ecfe29258b56001cfe37592c",
    "server/result.json": "5b8937402ac5b7104d9a08bc34f5b3899b54893e61993ee6d7ce9f3e975eb4ad",
    "server/stderr.log": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "server/stdout.log": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "server_config.json": "f183acf7b6927de8be36f2bd8775b8ced93d434da91859ba30b1c29123c1a5a2",
    "wire/10_request_0.bin": "57aaf8cd16f04a7d81039783ab3edacc7feb600baca10cc989cf062c791167f3",
    "wire/10_response_1.bin": "d3f0bb24192211826ce1f7f43941af40bce09ef2d29c5cc1d3e4d5e1107c8096",
    "wire/11_request_0.bin": "4931a03a4cb18f6ca58a756d94f5f906e32880f4e2d53ad6429e1a4056c93a15",
    "wire/11_response_1.bin": "ebd168c987dead566414d998ad4c8edc97fdeb82600678de941c9297577dd2ca",
    "wire/12_request_0.bin": "c0fa5ef42a939204cb92c48505cbb0c163ac3769e83d372ecfecad392f374fb2",
    "wire/12_response_1.bin": "37e16693d80ed3a86eab2d97568558fb419296d3d1bc630d324ae6e595054806",
    "wire/13_request_0.bin": "51e5d1a1ea2a7b9f2d479c0ad405827450679b18d18b0f4c7354a231a7df8d8a",
    "wire/13_response_1.bin": "debb29d72ac6c8df9dabe2165edf97c14e81368fab3e9e8b44f396a95dc0d0b1",
    "wire/14_request_0.bin": "40a7a2bd38238fcf95828e5bab0e77f1d942f91465d401fce0f1e085f596c623",
    "wire/14_response_1.bin": "42d7199e0ab7ef609bd17bb6d55ec994aa860a6ea0f45e5f4e512684dd713bb3",
    "wire/15_request_0.bin": "6986e200882bbb4eb8d0043dc5eaae7144adac244c52008b57fe699cddfbabe8",
    "wire/15_response_1.bin": "335b42b885f3b7d45e29581856e6cb4e046303c88fc59b95436c25908617d9fa",
    "wire/16_request_0.bin": "8bc3a220257dc910ffa69d64411c99e1cfc0925d130c28be57bc34880da576f7",
    "wire/16_response_1.bin": "25ceeb5fea99048976b6ed3e70da55423147a638d1c0c9c29d5b00f6302ab0fb",
    "wire/17_request_0.bin": "15a0a900a4cea253aa34a91392baf75100c7f9123564a3a0524ba071b8c28d4e",
    "wire/17_response_1.bin": "fe644d8a0c67bdffaf341efe4a47c19af3a0fb7a60ccde3b86452dd1c89e16c3",
    "
```

### `apu_characterization\out\mcp_tax\fixphase_resmoke_v10\runs\http_sse_tls_off\t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-stripped\0\COMPLETE.json`
- keys: ['cell_id', 'cell_plan_sha256', 'complete', 'files', 'layout_version', 'protocol_version', 'seed']
  - `cell_id`: str
  - `cell_plan_sha256`: str
  - `complete`: bool
  - `files`: dict
  - `files.client/result.json`: str
  - `files.manifest.json`: str
  - `files.plan.json`: str
  - `files.server/result.json`: str
  - `files.server/stderr.log`: str
  - `files.server/stdout.log`: str
  - `files.server_config.json`: str
  - `files.wire/10_request_0.bin`: str
  - `files.wire/10_response_1.bin`: str
  - `files.wire/11_request_0.bin`: str
  - `files.wire/11_response_1.bin`: str
  - `files.wire/12_request_0.bin`: str
  - `files.wire/12_response_1.bin`: str
  - `files.wire/13_request_0.bin`: str
  - `files.wire/13_response_1.bin`: str
  - `files.wire/14_request_0.bin`: str
  - `files.wire/14_response_1.bin`: str
  - `files.wire/15_request_0.bin`: str
  - `files.wire/15_response_1.bin`: str
  - `files.wire/16_request_0.bin`: str
  - `files.wire/16_response_1.bin`: str
  - `files.wire/17_request_0.bin`: str
  - `files.wire/17_response_1.bin`: str
  - `files.wire/18_request_0.bin`: str
  - `files.wire/18_response_1.bin`: str
  - `files.wire/19_request_0.bin`: str
  - `files.wire/19_response_1.bin`: str
  - `files.wire/1_request_0.bin`: str
  - `files.wire/1_response_1.bin`: str
  - `files.wire/20_request_0.bin`: str
  - `files.wire/20_response_1.bin`: str
  - `files.wire/2_request_0.bin`: str
  - `files.wire/2_response_1.bin`: str
  - `files.wire/3_request_0.bin`: str
  - `files.wire/3_response_1.bin`: str
  - `files.wire/4_request_0.bin`: str
  - `files.wire/4_response_1.bin`: str
  - `files.wire/5_request_0.bin`: str
  - `files.wire/5_response_1.bin`: str
  - `files.wire/6_request_0.bin`: str
  - `files.wire/6_response_1.bin`: str
  - `files.wire/7_request_0.bin`: str
  - `files.wire/7_response_1.bin`: str
  - `files.wire/8_request_0.bin`: str
  - `files.wire/8_response_1.bin`: str
  - `files.wire/9_request_0.bin`: str
  - `files.wire/9_response_1.bin`: str
  - `layout_version`: int
  - `protocol_version`: str
  - `seed`: int
```json
{
  "cell_id": "t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-stripped",
  "cell_plan_sha256": "989549aa01eb1ca6935d1d4b4a04a0d7ee2dba91c9915e93d37b6d7508483ee0",
  "complete": true,
  "files": {
    "client/result.json": "73de4a523e70889e422116b1c3884eeba36865e6bb923fed1ddf8f25e5143566",
    "manifest.json": "237fb5b8694ca8dd3386b8c5657ad5744825034a9246ca63583d12a26caf9664",
    "plan.json": "2e6c9f437a1426f026892d6dcbe62b1c214ac718fa864aa8261500eaf672fc42",
    "server/result.json": "9fc13d6fde1a085835e715995a7d06f476e2564b4731e9e8a46c15cf33699030",
    "server/stderr.log": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "server/stdout.log": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "server_config.json": "fe3b356154b24c1b3b9ee676c2cdfe4bdac41f2c3925e92107f448a10923d262",
    "wire/10_request_0.bin": "455219cd160e26324647f77f6726e29b95080b6aee7d77791f1681c560a111c2",
    "wire/10_response_1.bin": "95e9ada1fb3f79a2674741fa21a4541a1704353e66d0fd072df2778dca2c88c6",
    "wire/11_request_0.bin": "7bc0e36a480a3e14235bdffc414f331d3e496a98de5f874c42ed62640a1aae9f",
    "wire/11_response_1.bin": "2298ba5ed2b70854518e906c83d3144b6114a3c280b99af09e32c4d1d1e9d317",
    "wire/12_request_0.bin": "85e483b735736ba4b7eaee22ab069b203283a541483aff6104b77b8276a81a1b",
    "wire/12_response_1.bin": "a00ff3b322cde5639acd2824257c81238f4c9a8fc6e0aa884e0be6679690d44d",
    "wire/13_request_0.bin": "9109d2f6dfd450283ef2eea0d76651208e9a0a45803050186a3253099b3f0262",
    "wire/13_response_1.bin": "d56eb7ab0a9515bc28302053bc928ab63719cac15d2b1eddf47cc940e8064cad",
    "wire/14_request_0.bin": "c771505959213b919ca89b7df4cbd7561ce435a53f760b8a110aa48c032d2f5d",
    "wire/14_response_1.bin": "921b8c58867664d8ceeb5f3bcc697b0beb9fbc656fbf7c664a21fb3f57419200",
    "wire/15_request_0.bin": "c8461cab4a2453f120581057ee98e7c0ac2c8e33ba9fdf2093871063f9374c42",
    "wire/15_response_1.bin": "f6fe8340741fd46ff9cd830421d626ca7b2f52d4cbf84125f54b341121f262c8",
    "wire/16_request_0.bin": "90234d73a38ca346214242d2bb4f03de4e0a80a2a8b2275ba1fe477c2376e8ae",
    "wire/16_response_1.bin": "fb37cf5855674466f675246b099bc12a5d78fb7a52de8ddaf047da433fbd871b",
    "wire/17_request_0.bin": "af5290401b8cc02277abf7eadacd0b0b95779b313f0a50b552af826945c264f0",
    "wire/17_response_1.bin": "82d1100e04ab2326756034b3194b831610c1dd2d305f2e991e228ce4c562a3dc",
    "wire/18_request_0.bin": "81714c402ecf6ffc96f117d16982248985ceaea526a933730a66519a9538a819",
```

### `apu_characterization\out\mcp_tax\fixphase_resmoke_v10\runs\http_sse_tls_off\t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-full\0\client\result.json`
- keys: ['canonical_hashes', 'categories', 'category_hooks_enabled', 'endpoint_observation', 'ledger_version', 'message_diagnostics', 'messages', 'mode', 'process_role', 'sdk_coverage', 'setup', 'setup_observation', 'waits', 'wire_captures']
  - `canonical_hashes`: list[str] len=20
  - `categories`: list[dict] len=100
  - `categories[].category`: str
  - `categories[].message_id`: str
  - `categories[].process_role`: str
  - `categories[].totals`: dict
  - `categories[].totals.bytes`: int
  - `categories[].totals.bytes_in`: int
  - `categories[].totals.bytes_out`: int
  - `categories[].totals.count`: int
  - `categories[].totals.cpu_ns`: int
  - `categories[].totals.provenance`: dict
  - `categories[].totals.provenance.client_call_inter_region_gaps`: int
  - `categories[].totals.provenance.client_result_dispatch`: int
  - `categories[].totals.wall_ns`: int
  - `category_hooks_enabled`: bool
  - `endpoint_observation`: dict
  - `endpoint_observation.end_wall_ns`: int
  - `endpoint_observation.metadata`: dict
  - `endpoint_observation.metadata.canonical_hashes`: list[str] len=20
  - `endpoint_observation.metadata.pid`: int
  - `endpoint_observation.metadata.timer_pair_cost_ns`: int
  - `endpoint_observation.process_cpu_ns`: int
  - `endpoint_observation.start_wall_ns`: int
  - `endpoint_observation.wall_ns`: int
  - `ledger_version`: str
  - `message_diagnostics`: dict
  - `message_diagnostics.1`: dict
  - `message_diagnostics.1.client_call_boundary_ns`: int
  - `message_diagnostics.1.client_call_boundary_wall_ns`: int
  - `message_diagnostics.1.client_nested_cpu_ns`: int
  - `message_diagnostics.1.gap_decomposition`: dict
  - `message_diagnostics.1.gap_decomposition.boundaries`: list[str] len=4
  - `message_diagnostics.1.gap_decomposition.diagnostics`: dict
  - `message_diagnostics.1.gap_decomposition.diagnostics.gap_segment_count`: int
  - `message_diagnostics.1.gap_decomposition.diagnostics.gc_interval_count`: int
  - `message_diagnostics.1.gap_decomposition.diagnostics.gc_stats_after`: list[dict] len=3
  - `message_diagnostics.1.gap_decomposition.diagnostics.gc_stats_before`: list[dict] len=3
  - `message_diagnostics.1.gap_decomposition.diagnostics.timer_pair_cost_ns`: int
  - `message_diagnostics.1.gap_decomposition.diagnostics.timer_pairs`: int
  - `message_diagnostics.1.gap_decomposition.gap_syscall_return_subprovenance`: dict
  - `message_diagnostics.1.gap_decomposition.gap_syscall_return_subprovenance.adjacent_segments_ns`: int
  - `message_diagnostics.1.gap_decomposition.gap_syscall_return_subprovenance.measured_ns`: int
  - `message_diagnostics.1.gap_decomposition.gap_syscall_return_subprovenance.note`: str
  - `message_diagnostics.1.gap_decomposition.mechanisms`: dict
  - `message_diagnostics.1.gap_decomposition.mechanisms.gap_event_loop`: int
  - `message_diagnostics.1.gap_decomposition.mechanisms.gap_gc`: int
  - `message_diagnostics.1.gap_decomposition.mechanisms.gap_instrumentation`: int
  - `message_diagnostics.1.gap_decomposition.mechanisms.gap_syscall_return`: int
  - `message_diagnostics.1.gap_decomposition.mechanisms.gap_unattributed`: int
  - `message_diagnostics.1.gap_decomposition.overlap_resolutions`: list[empty] len=0
  - `message_diagnostics.1.gap_decomposition.parent_cpu_ns`: int
  - `message_diagnostics.1.gap_decomposition.precedence`: list[str] len=4
  - `message_diagnostics.1.gap_decomposition.provenance_sites`: dict
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_event_loop`: str
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_gc`: str
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_instrumentation`: str
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_syscall_return`: str
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_syscall_return_adjacent`: str
  - `message_diagnostics.1.gap_decomposition.provenance_sites.gap_syscall_return_measured`: str
```json
{
  "canonical_hashes": [
    "5244654d65cf5872cba80503e067d9354edfb91fb9a0fc66d1d70f25e9f190de",
    "624bc4c8685aa3127a2a5bdc853600127361748d84649f534046cb34382eb487",
    "8c590203cd4548b3599a18b31859c763abd935a1e4a3d98fcc7a96ca5af7c6ec",
    "644ffee1a1b7475e26bc2367db5ca517a2ddae3d2c9b919947903bb0227af697",
    "5264bd7936f0974a118a2ac44d316b6bdccec6217d5796ed17e7c7a4d4bac6dc",
    "a402058799ebe5431202e48b30ea59510e9daa4896403655e56f2a1276d0593d",
    "8cca0e028cf304db2e7dbb2efe7496f7a1feab86b205e6bb042079bd3d2364d8",
    "3ac33f33e106da1a01c890b60b1aab6b1615c8d4abfafba1112608d8e9c1729a",
    "8bac07d83408e8d2120ec73adb52997052ec68d6895d67613839f805aec8dc70",
    "c5c477a93d55710cd9cc04b85a80b3702033935a170aa88b524f2d47d604304c",
    "37eb6e45885ffcca3f1ba716b66b69506d87be36d171201f25f03939e02b2aae",
    "01b563fcdcd77efa576960cf829d5cba6bb460204c732c39d11b5ced21af29a1",
    "1227d288c7494a9fdcfc0bf4593308fc48f57696109c93a1a9c8e04e4e499153",
    "1ed2d250aae2a4afb8a0c6fe281f3d5bc3fc7a23b54a84538bd2e04fbe5f1dec",
    "043b893ce9f7afa285c5cbb34be2f1f36f070d62841881ffda73cdb9a7cf151a",
    "de67f77770c0acfdf0e9906771fd94547a166b2f62ecbc5c287b7c995acd7c63",
    "992e2f361034d8f5f3a8d23912c6c1f3b2aee4748a506c4cb8d2fd8fef4c85ba",
    "d5ed66f89e1f1d0f354e49778c38e5b16deb87fdf8cc198d28a3a1232c003518",
    "3e8eea885025c5db7cb2e6b831249d47c36966cac6ca82b12f7ac5c04143b82f",
    "397a6dafd59abaebf95d6f55d67e4dba32187f4e853b6c48c9ab51ce20e18d24"
  ],
  "categories": [
    {
      "category": "MSG_DISPATCH",
      "message_id": "1",
      "process_role": "client",
      "totals": {
        "bytes": 0,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 2,
        "cpu_ns": 1407500,
        "provenance": {
          "client_call_inter_region_gaps": 1404843,
          "client_result_dispatch": 2657
        },
        "wall_ns": 1407500
      }
    },
    {
      "category": "MSG_DISPATCH",
      "message_id": "10",
      "process_role": "client",
      "totals": {
        "bytes": 0,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 2,
        "cpu_ns": 1171059,
        "provenance": {
          "client_call_inter_region_gaps": 1168272,
          "client_result_dispatch": 2787
        },
        "wall_ns": 1171059
      }
    },
    {
      "category": "MSG_DISPATCH",
      "message_id": "11",
      "process_role": "client",
      "totals": {
        "bytes": 0,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 2,
        "c
```

### `apu_characterization\out\mcp_tax\fixphase_resmoke_v10\runs\http_sse_tls_off\t-sse_plain__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-stripped\0\client\result.json`
- keys: ['canonical_hashes', 'categories', 'category_hooks_enabled', 'endpoint_observation', 'ledger_version', 'message_diagnostics', 'messages', 'mode', 'process_role', 'sdk_coverage', 'setup', 'setup_observation', 'waits', 'wire_captures']
  - `canonical_hashes`: list[str] len=20
  - `categories`: list[dict] len=1
  - `categories[].category`: str
  - `categories[].message_id`: str
  - `categories[].process_role`: str
  - `categories[].totals`: dict
  - `categories[].totals.bytes`: int
  - `categories[].totals.bytes_in`: int
  - `categories[].totals.bytes_out`: int
  - `categories[].totals.count`: int
  - `categories[].totals.cpu_ns`: int
  - `categories[].totals.provenance`: dict
  - `categories[].totals.provenance.endpoint_reconciliation`: int
  - `categories[].totals.wall_ns`: int
  - `category_hooks_enabled`: bool
  - `endpoint_observation`: dict
  - `endpoint_observation.end_wall_ns`: int
  - `endpoint_observation.metadata`: dict
  - `endpoint_observation.metadata.canonical_hashes`: list[str] len=20
  - `endpoint_observation.metadata.pid`: int
  - `endpoint_observation.metadata.timer_pair_cost_ns`: int
  - `endpoint_observation.process_cpu_ns`: int
  - `endpoint_observation.start_wall_ns`: int
  - `endpoint_observation.wall_ns`: int
  - `ledger_version`: str
  - `message_diagnostics`: dict
  - `message_diagnostics.1`: dict
  - `message_diagnostics.1.client_call_boundary_ns`: int
  - `message_diagnostics.1.client_call_boundary_wall_ns`: int
  - `message_diagnostics.1.client_nested_cpu_ns`: int
  - `message_diagnostics.10`: dict
  - `message_diagnostics.10.client_call_boundary_ns`: int
  - `message_diagnostics.10.client_call_boundary_wall_ns`: int
  - `message_diagnostics.10.client_nested_cpu_ns`: int
  - `message_diagnostics.11`: dict
  - `message_diagnostics.11.client_call_boundary_ns`: int
  - `message_diagnostics.11.client_call_boundary_wall_ns`: int
  - `message_diagnostics.11.client_nested_cpu_ns`: int
  - `message_diagnostics.12`: dict
  - `message_diagnostics.12.client_call_boundary_ns`: int
  - `message_diagnostics.12.client_call_boundary_wall_ns`: int
  - `message_diagnostics.12.client_nested_cpu_ns`: int
  - `message_diagnostics.13`: dict
  - `message_diagnostics.13.client_call_boundary_ns`: int
  - `message_diagnostics.13.client_call_boundary_wall_ns`: int
  - `message_diagnostics.13.client_nested_cpu_ns`: int
  - `message_diagnostics.14`: dict
  - `message_diagnostics.14.client_call_boundary_ns`: int
  - `message_diagnostics.14.client_call_boundary_wall_ns`: int
  - `message_diagnostics.14.client_nested_cpu_ns`: int
  - `message_diagnostics.15`: dict
  - `message_diagnostics.15.client_call_boundary_ns`: int
  - `message_diagnostics.15.client_call_boundary_wall_ns`: int
  - `message_diagnostics.15.client_nested_cpu_ns`: int
  - `message_diagnostics.16`: dict
  - `message_diagnostics.16.client_call_boundary_ns`: int
  - `message_diagnostics.16.client_call_boundary_wall_ns`: int
  - `message_diagnostics.16.client_nested_cpu_ns`: int
  - `message_diagnostics.17`: dict
  - `message_diagnostics.17.client_call_boundary_ns`: int
```json
{
  "canonical_hashes": [
    "5244654d65cf5872cba80503e067d9354edfb91fb9a0fc66d1d70f25e9f190de",
    "624bc4c8685aa3127a2a5bdc853600127361748d84649f534046cb34382eb487",
    "8c590203cd4548b3599a18b31859c763abd935a1e4a3d98fcc7a96ca5af7c6ec",
    "644ffee1a1b7475e26bc2367db5ca517a2ddae3d2c9b919947903bb0227af697",
    "5264bd7936f0974a118a2ac44d316b6bdccec6217d5796ed17e7c7a4d4bac6dc",
    "a402058799ebe5431202e48b30ea59510e9daa4896403655e56f2a1276d0593d",
    "8cca0e028cf304db2e7dbb2efe7496f7a1feab86b205e6bb042079bd3d2364d8",
    "3ac33f33e106da1a01c890b60b1aab6b1615c8d4abfafba1112608d8e9c1729a",
    "8bac07d83408e8d2120ec73adb52997052ec68d6895d67613839f805aec8dc70",
    "c5c477a93d55710cd9cc04b85a80b3702033935a170aa88b524f2d47d604304c",
    "37eb6e45885ffcca3f1ba716b66b69506d87be36d171201f25f03939e02b2aae",
    "01b563fcdcd77efa576960cf829d5cba6bb460204c732c39d11b5ced21af29a1",
    "1227d288c7494a9fdcfc0bf4593308fc48f57696109c93a1a9c8e04e4e499153",
    "1ed2d250aae2a4afb8a0c6fe281f3d5bc3fc7a23b54a84538bd2e04fbe5f1dec",
    "043b893ce9f7afa285c5cbb34be2f1f36f070d62841881ffda73cdb9a7cf151a",
    "de67f77770c0acfdf0e9906771fd94547a166b2f62ecbc5c287b7c995acd7c63",
    "992e2f361034d8f5f3a8d23912c6c1f3b2aee4748a506c4cb8d2fd8fef4c85ba",
    "d5ed66f89e1f1d0f354e49778c38e5b16deb87fdf8cc198d28a3a1232c003518",
    "3e8eea885025c5db7cb2e6b831249d47c36966cac6ca82b12f7ac5c04143b82f",
    "397a6dafd59abaebf95d6f55d67e4dba32187f4e853b6c48c9ab51ce20e18d24"
  ],
  "categories": [
    {
      "category": "RESIDUAL",
      "message_id": "20",
      "process_role": "client",
      "totals": {
        "bytes": 0,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 1,
        "cpu_ns": 29680744,
        "provenance": {
          "endpoint_reconciliation": 29680744
        },
        "wall_ns": 29680744
      }
    }
  ],
  "category_hooks_enabled": false,
  "endpoint_observation": {
    "end_wall_ns": 4867316968803,
    "metadata": {
      "canonical_hashes": [
        "5244654d65cf5872cba80503e067d9354edfb91fb9a0fc66d1d70f25e9f190de",
        "624bc4c8685aa3127a2a5bdc853600127361748d84649f534046cb34382eb487",
        "8c590203cd4548b3599a18b31859c763abd935a1e4a3d98fcc7a96ca5af7c6ec",
        "644ffee1a1b7475e26bc2367db5ca517a2ddae3d2c9b919947903bb0227af697",
        "5264bd7936f0974a118a2ac44d316b6bdccec6217d5796ed17e7c7a4d4bac6dc",
        "a402058799ebe5431202e48b30ea59510e9daa4896403655e56f2a1276d0593d",
        "8cca0e028cf304db2e7dbb2efe7496f7a1feab86b205e6bb0
```


## 6. Other out/ agent-run aggregates


### `apu_characterization\out\real_agent_breakdown.json` size=88677
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'task_assignments', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'category_regions_override', 'reproduce_cmd', 'per_task', 'category_averages', 'per_task_wall_cpu', 'behavior_buckets', 'amenability_tiers', 'invariant', 'audit']
  - `amenability_tiers`: dict
  - `amenability_tiers.CONTEXT_MGMT`: str
  - `amenability_tiers.GC`: str
  - `amenability_tiers.HTTP_CLIENT`: str
  - `amenability_tiers.LOGGING`: str
  - `amenability_tiers.ORCH_DISPATCH`: str
  - `amenability_tiers.ORCH_SETUP`: str
  - `amenability_tiers.PROMPT_ASSEMBLY`: str
  - `amenability_tiers.SERIALIZATION`: str
  - `amenability_tiers.TOKENIZATION`: str
  - `amenability_tiers.TOOL_COMPUTE`: str
  - `audit`: dict
  - `audit.min_quotable_session_cpu_ms`: float
  - `audit.n_seeds`: int
  - `audit.pass`: bool
  - `audit.platform`: str
  - `audit.publishable_ok`: bool
  - `audit.violations`: list[str] len=1
  - `audit.warnings`: list[str] len=9
  - `audit.windows_tick_ms`: float
  - `batch_wall_s`: float
  - `behavior_buckets`: dict
  - `behavior_buckets.buckets`: dict
  - `behavior_buckets.buckets.B0_io_only`: dict
  - `behavior_buckets.buckets.B0_io_only.label`: str
  - `behavior_buckets.buckets.B0_io_only.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B0_io_only.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B0_io_only.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B0_io_only.task_labels`: list[str] len=1
  - `behavior_buckets.buckets.B0_io_only.tasks`: list[str] len=1
  - `behavior_buckets.buckets.B1_search_only`: dict
  - `behavior_buckets.buckets.B1_search_only.label`: str
  - `behavior_buckets.buckets.B1_search_only.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B1_search_only.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B1_search_only.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B1_search_only.task_labels`: list[str] len=2
  - `behavior_buckets.buckets.B1_search_only.tasks`: list[str] len=3
  - `behavior_buckets.buckets.B3_retrieve_heavy`: dict
  - `behavior_buckets.buckets.B3_retrieve_heavy.label`: str
  - `behavior_buckets.buckets.B3_retrieve_heavy.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B3_retrieve_heavy.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B3_retrieve_heavy.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B3_retrieve_heavy.task_labels`: list[str] len=1
  - `behavior_buckets.buckets.B3_retrieve_heavy.tasks`: list[str] len=1
  - `behavior_buckets.buckets.B3_retrieve_light`: dict
  - `behavior_buckets.buckets.B3_retrieve_light.label`: str
  - `behavior_buckets.buckets.B3_retrieve_light.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B3_retrieve_light.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B3_retrieve_light.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B3_retrieve_light.task_labels`: list[str] len=3
  - `behavior_buckets.buckets.B3_retrieve_light.tasks`: list[str] len=3
  - `behavior_buckets.buckets.B4_code_light`: dict
  - `behavior_buckets.buckets.B4_code_light.label`: str
  - `behavior_buckets.buckets.B4_code_light.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B4_code_light.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B4_code_light.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B4_code_light.task_labels`: list[str] len=2
  - `behavior_buckets.buckets.B4_code_light.tasks`: list[str] len=2
  - `behavior_buckets.cpu_floor_ms`: float
  - `behavior_buckets.note`: str
  - `behavior_buckets.session_meta`: dict
  - `behavior_buckets.session_meta.CH-01`: dict
  - `behavior_buckets.session_meta.CH-01.above_cpu_floor`: bool
  - `behavior_buckets.session_meta.CH-01.behavior_bucket`: str
  - `behavior_buckets.session_meta.CH-01.behavior_label`: str
  - `behavior_buckets.session_meta.CH-01.host_cpu_ms`: float
  - `behavior_buckets.session_meta.CH-01.task_label`: str
  - `behavior_buckets.session_meta.CH-01.tool_call_counts`: dict
  - `behavior_buckets.session_meta.CH-01.tool_call_counts.calculator`: int
  - `behavior_buckets.session_meta.CH-01.tool_call_counts.code_exec`: int
  - `behavior_buckets.session_meta.CH-01.turns`: int
  - `behavior_buckets.session_meta.CH-02`: dict
  - `behavior_buckets.session_meta.CH-02.above_cpu_floor`: bool
  - `behavior_buckets.session_meta.CH-02.behavior_bucket`: str
  - `behavior_buckets.session_meta.CH-02.behavior_label`: str
  - `behavior_buckets.session_meta.CH-02.host_cpu_ms`: float
  - `behavior_buckets.session_meta.CH-02.task_label`: str
  - `behavior_buckets.session_meta.CH-02.tool_call_counts`: dict
  - `behavior_buckets.session_meta.CH-02.tool_call_counts.calculator`: int
  - `behavior_buckets.session_meta.CH-02.tool_call_counts.retrieve`: int
- `per_task` count: 10
```json
{
  "experiment": "real_agent_breakdown",
  "result_validity": "audit_failed",
  "generated_utc": "2026-07-07T18:49:17.234689+00:00",
  "setup_ref": {
    "setup_digest": "be14904706711ea6",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 325"
  },
  "task_assignments": [
    {
      "task_id": "SH-01",
      "profile": "search_heavy",
      "goal": "What causes different kinds of weather? Collect mentions of rain, storms, and temperature changes and summarize the patterns.",
      "turns": [
        "search <- rain storm",
        "search <- temperature cold warm",
        "search <- wind forecast",
        "search <- snow season",
        "search <- climate humidity",
        "search <- cloud sun",
        "calculator <- (72 - 32) * 5 / 9",
        "search <- storm wind rain",
        "search <- season climate",
        "reasoning only"
      ]
    },
    {
      "task_id": "SH-02",
      "profile": "search_heavy",
      "goal": "Put together a short overview of space topics: find what the corpus says about planets, the moon, eclipses, and telescopes.",
      "turns": [
        "search <- planet orbit",
        "search <- moon eclipse",
        "search <- solar eclipse",
        "search <- telescope star",
        "search <- rocket astronaut",
        "retrieve <- which planets can be seen without a telescope",
        "search <- mars earth",
        "search <- gravity light",
        "search <- galaxy star",
        "search <- orbit gravity",
        "reasoning only"
      ]
    },
    {
      "task_id": "CH-01",
      "profile": "code_heavy",
      "goal": "What is the sum of all prime numbers below 20000? Verify with a second computation and sanity-check the magnitude.",
      "turns": [
        "code_exec <- limit = 20000 sieve = [True] * limit sieve[0] = sieve[1] = False for i in range(2, int(limit ** 0.5)",
        "code_exec <- xs = [(i * 2654435761) % 100003 for i in range(30000)] xs.sort() result = xs[len(xs) // 2]",
        "calculator <- 21171191 / 1000000",
        "code_exec <- a, b = 0, 1 for _ in range(50000):     a, b = b, (a + b) % 1000000007 result = a",
        "reasoning only"
      ]
    },
    {
      "task_id": "CH-02",
      "profile": "code_heavy",
      "goal": "If I save 1000 dollars at 5 percent interest for 30 years, how much do I have? Also check a word-frequency count and a median.",
      "turns": [
        "code_exec <- balance = 1000.0 rate = 0.05 for year in range(30):     balanc
```

### `apu_characterization\out\real_agent_breakdown_remote_search.json` size=28648
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'task_assignments', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'category_regions_override', 'reproduce_cmd', 'per_task', 'category_averages', 'per_task_wall_cpu', 'behavior_buckets', 'amenability_tiers', 'invariant', 'batch_attribution', 'audit']
  - `amenability_tiers`: dict
  - `amenability_tiers.CLIENT_HTTP`: str
  - `amenability_tiers.CLIENT_PARSE`: str
  - `amenability_tiers.CONTEXT_MGMT`: str
  - `amenability_tiers.EVENT_LOOP`: str
  - `amenability_tiers.FRAMEWORK`: str
  - `amenability_tiers.GC`: str
  - `amenability_tiers.HTTP_CLIENT`: str
  - `amenability_tiers.LOGGING`: str
  - `amenability_tiers.ORCH_DISPATCH`: str
  - `amenability_tiers.ORCH_SETUP`: str
  - `amenability_tiers.PROMPT_ASSEMBLY`: str
  - `amenability_tiers.RESIDUAL_UNATTRIBUTED`: str
  - `amenability_tiers.SERIALIZATION`: str
  - `amenability_tiers.THREADPOOL`: str
  - `amenability_tiers.TOKENIZATION`: str
  - `amenability_tiers.TOOL_COMPUTE`: str
  - `audit`: dict
  - `audit.attribution_summary`: dict
  - `audit.attribution_summary.orch_measured_pct_of_host`: float
  - `audit.attribution_summary.orch_reconcile_pct_of_host`: float
  - `audit.attribution_summary.orch_reconcile_pct_of_orch`: float
  - `audit.min_quotable_session_cpu_ms`: float
  - `audit.n_seeds`: int
  - `audit.pass`: bool
  - `audit.platform`: str
  - `audit.publishable_ok`: bool
  - `audit.violations`: list[empty] len=0
  - `audit.warnings`: list[str] len=2
  - `audit.windows_tick_ms`: NoneType
  - `batch_attribution`: dict
  - `batch_attribution.batch_host_cpu_ms`: float
  - `batch_attribution.execution_note`: str
  - `batch_attribution.harness_broad_definition`: str
  - `batch_attribution.harness_strict_definition`: str
  - `batch_attribution.orch_measured_pct_of_orch`: float
  - `batch_attribution.orch_reconcile_pct_of_orch`: float
  - `batch_attribution.pooled_client_http_pct`: float
  - `batch_attribution.pooled_client_parse_pct`: float
  - `batch_attribution.pooled_event_loop_pct`: float
  - `batch_attribution.pooled_framework_pct`: float
  - `batch_attribution.pooled_harness_apu_pct`: float
  - `batch_attribution.pooled_harness_broad_pct`: float
  - `batch_attribution.pooled_harness_strict_pct`: float
  - `batch_attribution.pooled_measured_pct`: float
  - `batch_attribution.pooled_orch_measured_pct`: float
  - `batch_attribution.pooled_orch_pct`: float
  - `batch_attribution.pooled_orch_reconcile_pct`: float
  - `batch_attribution.pooled_residual_provenance_pct`: float
  - `batch_attribution.pooled_residual_unattributed_pct`: float
  - `batch_attribution.pooled_step_inferred_pct`: float
  - `batch_attribution.pooled_threadpool_pct`: float
  - `batch_attribution.pooled_tool_compute_pct`: float
  - `batch_wall_s`: float
  - `behavior_buckets`: dict
  - `behavior_buckets.buckets`: dict
  - `behavior_buckets.buckets.B1_search_only`: dict
  - `behavior_buckets.buckets.B1_search_only.label`: str
  - `behavior_buckets.buckets.B1_search_only.mean_amenable_broad`: float
  - `behavior_buckets.buckets.B1_search_only.mean_amenable_strict`: float
  - `behavior_buckets.buckets.B1_search_only.mean_host_cpu_ms`: float
  - `behavior_buckets.buckets.B1_search_only.task_labels`: list[str] len=1
  - `behavior_buckets.buckets.B1_search_only.tasks`: list[str] len=1
  - `behavior_buckets.cpu_floor_ms`: float
  - `behavior_buckets.note`: str
  - `behavior_buckets.session_meta`: dict
  - `behavior_buckets.session_meta.FO-01`: dict
  - `behavior_buckets.session_meta.FO-01.above_cpu_floor`: bool
  - `behavior_buckets.session_meta.FO-01.behavior_bucket`: str
  - `behavior_buckets.session_meta.FO-01.behavior_label`: str
  - `behavior_buckets.session_meta.FO-01.host_cpu_ms`: float
  - `behavior_buckets.session_meta.FO-01.task_label`: str
  - `behavior_buckets.session_meta.FO-01.tool_call_counts`: dict
  - `behavior_buckets.session_meta.FO-01.tool_call_counts.search`: int
  - `behavior_buckets.session_meta.FO-01.turns`: int
  - `category_averages`: dict
  - `category_averages.by_archetype`: dict
  - `category_averages.by_archetype.FO`: dict
  - `category_averages.by_archetype.FO.categories`: dict
  - `category_averages.by_archetype.FO.categories.CLIENT_HTTP`: dict
- `per_task` count: 1
```json
{
  "experiment": "real_agent_breakdown",
  "result_validity": "publishable",
  "generated_utc": "2026-07-08T13:18:01.396588+00:00",
  "setup_ref": {
    "setup_digest": "b375dc13337b83a8",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 325"
  },
  "task_assignments": [
    {
      "task_id": "FO-01",
      "profile": "fanout",
      "goal": "Compare the weather, best food, and main attractions of Paris, Tokyo, and Cairo. Nine searches fan out in one turn; their completions land nearly simultaneously (dispatch burst), then one merge turn.",
      "turns": [
        "fan-out 9 calls [search: paris weather forecast rain; search: paris food recipe cheese; search: paris museum castle history; search: tokyo weather season wind; search: tokyo food fish dinner; search: tokyo city station bridge; search: cairo weather sun warm; search: cairo food bread market; search: cairo ancient museum empire]",
        "reasoning only"
      ]
    }
  ],
  "git": {
    "commit": "7decfdc59faababef3f4695622ba3eb75f7e39e6",
    "dirty": "yes",
    "dirty_paths": [
      "apu_characterization/run_apu_gate.sh",
      "apu_characterization/tools/_llm_wait_vs_host.py"
    ]
  },
  "env": {
    "python": "3.14.4",
    "platform": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43",
    "cpu_model": "unknown",
    "blas_pin": {
      "OPENBLAS_NUM_THREADS": "1",
      "MKL_NUM_THREADS": "1",
      "OMP_NUM_THREADS": "1"
    },
    "cores_logical": 8,
    "cores_physical": 8,
    "ram_gb": 7.56
  },
  "config": {
    "profile": "fanout",
    "payload_profile": "locality_ablation",
    "search_locality": "remote",
    "seed": 1,
    "sessions": 1,
    "mode": "threads/openai",
    "llm_median_scale": 0.05,
    "note_llm_scale": "scripted backend sleeps (wall only); openai backend ignores this",
    "total_cpu_basis": "sum(session process_time)",
    "comparison_type": "single_run_distribution_sample",
    "workers": 1,
    "execution": "sequential (workers=1, one session at a time)",
    "instr_version": 3
  },
  "timer_overhead_ns_per_pair": 6963.8217,
  "batch_wall_s": 73.47452142899996,
  "run": {
    "env": {},
    "config": {
      "concurrency": 1,
      "profile": "fanout",
      "payload_profile": "locality_ablation",
      "search_locality": "remote",
      "seed": 1,
      "mode": "threads",
      "backend": "openai",
      "llm_median_scale": 0.05,
      "workers": 1,
      "total_cpu_basis": "process_time_all_threads",
  
```

### `apu_characterization\out\replication_remote_search_v3.json` size=811583
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'git', 'measurement_git', 'env', 'config', 'aggregate', 'per_seed_artifacts', 'audit']
  - `aggregate`: dict
  - `aggregate.attribution_doc`: str
  - `aggregate.batch_host_cpu_ms`: dict
  - `aggregate.batch_host_cpu_ms.iqr`: float
  - `aggregate.batch_host_cpu_ms.max`: float
  - `aggregate.batch_host_cpu_ms.median`: float
  - `aggregate.batch_host_cpu_ms.min`: float
  - `aggregate.batch_host_cpu_ms.n`: float
  - `aggregate.batch_host_cpu_ms.q1`: float
  - `aggregate.batch_host_cpu_ms.q3`: float
  - `aggregate.comparison_type`: str
  - `aggregate.harness_broad_definition`: str
  - `aggregate.harness_strict_definition`: str
  - `aggregate.n_seeds`: int
  - `aggregate.orch_reconcile_share_of_orch_pct`: dict
  - `aggregate.orch_reconcile_share_of_orch_pct.iqr`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.max`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.median`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.min`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.n`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.q1`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.q3`: float
  - `aggregate.per_task_host_cpu_ms`: dict
  - `aggregate.per_task_host_cpu_ms.CH-01`: dict
  - `aggregate.per_task_host_cpu_ms.CH-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.max`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.median`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.min`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.n`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.CH-02`: dict
  - `aggregate.per_task_host_cpu_ms.CH-02.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.max`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.median`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.min`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.n`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.q1`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.q3`: float
  - `aggregate.per_task_host_cpu_ms.CN-01`: dict
  - `aggregate.per_task_host_cpu_ms.CN-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.max`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.median`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.min`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.n`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.FO-01`: dict
  - `aggregate.per_task_host_cpu_ms.FO-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.max`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.median`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.min`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.n`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.LH-01`: dict
  - `aggregate.per_task_host_cpu_ms.LH-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.max`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.median`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.min`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.n`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.LH-02`: dict
  - `aggregate.per_task_host_cpu_ms.LH-02.iqr`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.max`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.median`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.min`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.n`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.q1`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.q3`: float
  - `aggregate.per_task_host_cpu_ms.RE-01`: dict
  - `aggregate.per_task_host_cpu_ms.RE-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.max`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.median`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.min`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.n`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.RE-02`: dict
```json
{
  "experiment": "replication_batch",
  "result_validity": "publishable",
  "generated_utc": "2026-07-08T12:36:35.008714+00:00",
  "setup_ref": {
    "setup_digest": "6da6d4433aa84601",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 325"
  },
  "git": {
    "commit": "d5fd7b8b441565331154c6aeb599ba5863bed9c8",
    "dirty": "no",
    "dirty_paths": []
  },
  "measurement_git": {
    "commit": "d5fd7b8b441565331154c6aeb599ba5863bed9c8",
    "dirty": "no",
    "dirty_paths": []
  },
  "env": {
    "python": "3.14.4",
    "platform": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43",
    "cpu_model": "unknown",
    "blas_pin": {
      "OPENBLAS_NUM_THREADS": "1",
      "MKL_NUM_THREADS": "1",
      "OMP_NUM_THREADS": "1"
    },
    "cores_logical": 8,
    "cores_physical": 8,
    "ram_gb": 7.56
  },
  "config": {
    "profile": "mixed",
    "search_locality": "remote",
    "seeds": [
      0,
      1,
      2,
      3,
      4
    ],
    "sessions": 10,
    "backend": "openai",
    "comparison_type": "distribution_over_seeds",
    "allow_dirty": false,
    "instr_version": 3
  },
  "aggregate": {
    "n_seeds": 5,
    "seeds": [
      0,
      1,
      2,
      3,
      4
    ],
    "batch_host_cpu_ms": {
      "median": 2066.759393,
      "q1": 1606.703632,
      "q3": 2206.820493,
      "iqr": 600.1168610000002,
      "n": 5.0,
      "min": 1323.626487,
      "max": 2410.231715
    },
    "pooled_tool_compute_pct": {
      "median": 20.531115473323336,
      "q1": 17.091057861214807,
      "q3": 27.251784664535805,
      "iqr": 10.160726803320998,
      "n": 5.0,
      "min": 15.892447718513889,
      "max": 49.730717767083924
    },
    "pooled_orch_pct": {
      "median": 29.528667327129426,
      "q1": 27.052432218563627,
      "q3": 29.79856391110512,
      "iqr": 2.7461316925414927,
      "n": 5.0,
      "min": 18.696097045895975,
      "max": 36.37899789141058
    },
    "pooled_orch_measured_pct": {
      "median": 29.528667327129426,
      "q1": 27.052432218563627,
      "q3": 29.79856391110512,
      "iqr": 2.7461316925414927,
      "n": 5.0,
      "min": 18.696097045895975,
      "max": 36.37899789141058
    },
    "pooled_orch_reconcile_pct": {
      "median": 0.0,
      "q1": 0.0,
      "q3": 0.0,
      "iqr": 0.0,
      "n": 5.0,
      "min": 0.0,
      "max": 0.0
    },
    "pooled_harness_apu_pct": {
      "median": 36.44112827427878,
      "q1": 34.002555239135724,
      "q3": 43.707820
```

### `apu_characterization\out\replication_remote_search.json` size=615545
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'git', 'env', 'config', 'aggregate', 'per_seed_artifacts', 'audit', 'refreshed_utc', 'measurement_git']
  - `aggregate`: dict
  - `aggregate.attribution_doc`: str
  - `aggregate.batch_host_cpu_ms`: dict
  - `aggregate.batch_host_cpu_ms.iqr`: float
  - `aggregate.batch_host_cpu_ms.max`: float
  - `aggregate.batch_host_cpu_ms.median`: float
  - `aggregate.batch_host_cpu_ms.min`: float
  - `aggregate.batch_host_cpu_ms.n`: float
  - `aggregate.batch_host_cpu_ms.q1`: float
  - `aggregate.batch_host_cpu_ms.q3`: float
  - `aggregate.comparison_type`: str
  - `aggregate.harness_strict_definition`: str
  - `aggregate.n_seeds`: int
  - `aggregate.orch_reconcile_share_of_orch_pct`: dict
  - `aggregate.orch_reconcile_share_of_orch_pct.iqr`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.max`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.median`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.min`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.n`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.q1`: float
  - `aggregate.orch_reconcile_share_of_orch_pct.q3`: float
  - `aggregate.per_task_host_cpu_ms`: dict
  - `aggregate.per_task_host_cpu_ms.CH-01`: dict
  - `aggregate.per_task_host_cpu_ms.CH-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.max`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.median`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.min`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.n`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.CH-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.CH-02`: dict
  - `aggregate.per_task_host_cpu_ms.CH-02.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.max`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.median`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.min`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.n`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.q1`: float
  - `aggregate.per_task_host_cpu_ms.CH-02.q3`: float
  - `aggregate.per_task_host_cpu_ms.CN-01`: dict
  - `aggregate.per_task_host_cpu_ms.CN-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.max`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.median`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.min`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.n`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.CN-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.FO-01`: dict
  - `aggregate.per_task_host_cpu_ms.FO-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.max`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.median`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.min`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.n`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.FO-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.LH-01`: dict
  - `aggregate.per_task_host_cpu_ms.LH-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.max`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.median`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.min`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.n`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.LH-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.LH-02`: dict
  - `aggregate.per_task_host_cpu_ms.LH-02.iqr`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.max`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.median`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.min`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.n`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.q1`: float
  - `aggregate.per_task_host_cpu_ms.LH-02.q3`: float
  - `aggregate.per_task_host_cpu_ms.RE-01`: dict
  - `aggregate.per_task_host_cpu_ms.RE-01.iqr`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.max`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.median`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.min`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.n`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.q1`: float
  - `aggregate.per_task_host_cpu_ms.RE-01.q3`: float
  - `aggregate.per_task_host_cpu_ms.RE-02`: dict
  - `aggregate.per_task_host_cpu_ms.RE-02.iqr`: float
```json
{
  "experiment": "replication_batch",
  "result_validity": "publishable",
  "generated_utc": "2026-07-07T19:56:33.343327+00:00",
  "setup_ref": {
    "setup_digest": "66f54ae8c07ef581",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "unknown"
  },
  "git": {
    "commit": "db2266c124bf048e783f967835114822b605a140",
    "dirty": "no",
    "dirty_paths": []
  },
  "env": {
    "python": "3.14.4",
    "platform": "Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43",
    "cpu_model": "unknown",
    "cores_logical": 8,
    "cores_physical": 8,
    "ram_gb": 7.56
  },
  "config": {
    "profile": "mixed",
    "search_locality": "remote",
    "seeds": [
      0,
      1,
      2,
      3,
      4
    ],
    "sessions": 10,
    "backend": "openai",
    "comparison_type": "distribution_over_seeds"
  },
  "aggregate": {
    "n_seeds": 5,
    "seeds": [
      0,
      1,
      2,
      3,
      4
    ],
    "batch_host_cpu_ms": {
      "median": 8830.08077,
      "q1": 7525.261478,
      "q3": 10144.44508,
      "iqr": 2619.183601999999,
      "n": 5.0,
      "min": 6901.255984,
      "max": 13666.934924
    },
    "pooled_tool_compute_pct": {
      "median": 8.041480888212767,
      "q1": 7.333025365474217,
      "q3": 9.110150121537337,
      "iqr": 1.7771247560631203,
      "n": 5.0,
      "min": 5.529525787621289,
      "max": 37.351335830781586
    },
    "pooled_orch_pct": {
      "median": 79.57801920016419,
      "q1": 77.74240059436244,
      "q3": 83.16161497580502,
      "iqr": 5.419214381442586,
      "n": 5.0,
      "min": 59.87835613577002,
      "max": 89.39936491937306
    },
    "pooled_orch_measured_pct": {
      "median": 3.9542434831091464,
      "q1": 2.4760421183081065,
      "q3": 4.051578998183954,
      "iqr": 1.5755368798758478,
      "n": 5.0,
      "min": 2.276497405021192,
      "max": 4.877118144970324
    },
    "pooled_orch_reconcile_pct": {
      "median": 75.62377571705504,
      "q1": 72.86528244939213,
      "q3": 79.11003597762108,
      "iqr": 6.244753528228955,
      "n": 5.0,
      "min": 57.60185873074883,
      "max": 86.92332280106494
    },
    "pooled_harness_apu_pct": {
      "median": 84.03085072405568,
      "q1": 81.21358307438204,
      "q3": 85.66840959938354,
      "iqr": 4.454826525001494,
      "n": 5.0,
      "min": 60.484286844796046,
      "max": 90.91774423524723
    },
    "pooled_harness_strict_pct": {
      "median": 84.03085072405568,
      "q1": 81.21358307438204,
      "q3": 85
```

### `apu_characterization\out\single_agent_breakdown_debug.json` size=66063
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'task_assignments', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'per_task', 'category_averages', 'amenability_tiers', 'invariant']
  - `amenability_tiers`: dict
  - `amenability_tiers.CONTEXT_MGMT`: str
  - `amenability_tiers.GC`: str
  - `amenability_tiers.HTTP_CLIENT`: str
  - `amenability_tiers.LOGGING`: str
  - `amenability_tiers.ORCH_DISPATCH`: str
  - `amenability_tiers.ORCH_SETUP`: str
  - `amenability_tiers.PROMPT_ASSEMBLY`: str
  - `amenability_tiers.SERIALIZATION`: str
  - `amenability_tiers.TOKENIZATION`: str
  - `amenability_tiers.TOOL_COMPUTE`: str
  - `batch_wall_s`: float
  - `category_averages`: dict
  - `category_averages.by_archetype`: dict
  - `category_averages.by_archetype.CH`: dict
  - `category_averages.by_archetype.CH.categories`: dict
  - `category_averages.by_archetype.CH.categories.CONTEXT_MGMT`: dict
  - `category_averages.by_archetype.CH.categories.LOGGING`: dict
  - `category_averages.by_archetype.CH.categories.ORCH_DISPATCH`: dict
  - `category_averages.by_archetype.CH.categories.ORCH_SETUP`: dict
  - `category_averages.by_archetype.CH.categories.PROMPT_ASSEMBLY`: dict
  - `category_averages.by_archetype.CH.categories.SERIALIZATION`: dict
  - `category_averages.by_archetype.CH.categories.TOKENIZATION`: dict
  - `category_averages.by_archetype.CH.categories.TOOL_COMPUTE`: dict
  - `category_averages.by_archetype.CH.label`: str
  - `category_averages.by_archetype.CH.mean_amenable_broad_share`: float
  - `category_averages.by_archetype.CH.mean_amenable_strict_share`: float
  - `category_averages.by_archetype.CH.mean_instrumented_cpu_ms`: float
  - `category_averages.by_archetype.CH.mean_session_wall_s`: float
  - `category_averages.by_archetype.CH.mean_wall_frac_sum_partition`: float
  - `category_averages.by_archetype.CH.task_count`: int
  - `category_averages.by_archetype.CH.tasks`: list[str] len=2
  - `category_averages.by_archetype.LH`: dict
  - `category_averages.by_archetype.LH.categories`: dict
  - `category_averages.by_archetype.LH.categories.CONTEXT_MGMT`: dict
  - `category_averages.by_archetype.LH.categories.LOGGING`: dict
  - `category_averages.by_archetype.LH.categories.ORCH_DISPATCH`: dict
  - `category_averages.by_archetype.LH.categories.ORCH_SETUP`: dict
  - `category_averages.by_archetype.LH.categories.PROMPT_ASSEMBLY`: dict
  - `category_averages.by_archetype.LH.categories.SERIALIZATION`: dict
  - `category_averages.by_archetype.LH.categories.TOKENIZATION`: dict
  - `category_averages.by_archetype.LH.categories.TOOL_COMPUTE`: dict
  - `category_averages.by_archetype.LH.label`: str
  - `category_averages.by_archetype.LH.mean_amenable_broad_share`: float
  - `category_averages.by_archetype.LH.mean_amenable_strict_share`: float
  - `category_averages.by_archetype.LH.mean_instrumented_cpu_ms`: float
  - `category_averages.by_archetype.LH.mean_session_wall_s`: float
  - `category_averages.by_archetype.LH.mean_wall_frac_sum_partition`: float
  - `category_averages.by_archetype.LH.task_count`: int
  - `category_averages.by_archetype.LH.tasks`: list[str] len=2
  - `category_averages.by_archetype.RE`: dict
  - `category_averages.by_archetype.RE.categories`: dict
  - `category_averages.by_archetype.RE.categories.CONTEXT_MGMT`: dict
  - `category_averages.by_archetype.RE.categories.LOGGING`: dict
  - `category_averages.by_archetype.RE.categories.ORCH_DISPATCH`: dict
  - `category_averages.by_archetype.RE.categories.ORCH_SETUP`: dict
  - `category_averages.by_archetype.RE.categories.PROMPT_ASSEMBLY`: dict
  - `category_averages.by_archetype.RE.categories.SERIALIZATION`: dict
  - `category_averages.by_archetype.RE.categories.TOKENIZATION`: dict
  - `category_averages.by_archetype.RE.categories.TOOL_COMPUTE`: dict
  - `category_averages.by_archetype.RE.label`: str
  - `category_averages.by_archetype.RE.mean_amenable_broad_share`: float
  - `category_averages.by_archetype.RE.mean_amenable_strict_share`: float
  - `category_averages.by_archetype.RE.mean_instrumented_cpu_ms`: float
  - `category_averages.by_archetype.RE.mean_session_wall_s`: float
  - `category_averages.by_archetype.RE.mean_wall_frac_sum_partition`: float
  - `category_averages.by_archetype.RE.task_count`: int
  - `category_averages.by_archetype.RE.tasks`: list[str] len=2
  - `category_averages.by_archetype.RH`: dict
  - `category_averages.by_archetype.RH.categories`: dict
  - `category_averages.by_archetype.RH.categories.CONTEXT_MGMT`: dict
  - `category_averages.by_archetype.RH.categories.LOGGING`: dict
  - `category_averages.by_archetype.RH.categories.ORCH_DISPATCH`: dict
  - `category_averages.by_archetype.RH.categories.ORCH_SETUP`: dict
  - `category_averages.by_archetype.RH.categories.PROMPT_ASSEMBLY`: dict
  - `category_averages.by_archetype.RH.categories.SERIALIZATION`: dict
  - `category_averages.by_archetype.RH.categories.TOKENIZATION`: dict
  - `category_averages.by_archetype.RH.categories.TOOL_COMPUTE`: dict
  - `category_averages.by_archetype.RH.label`: str
  - `category_averages.by_archetype.RH.mean_amenable_broad_share`: float
- `per_task` count: 10
```json
{
  "experiment": "single_agent_breakdown",
  "result_validity": "debug_only",
  "generated_utc": "2026-07-07T16:39:15.072740+00:00",
  "setup_ref": {
    "setup_digest": "fe9707b03e17a5b7",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 325"
  },
  "task_assignments": [
    {
      "task_id": "SH-01",
      "profile": "search_heavy",
      "goal": "What causes different kinds of weather? Collect mentions of rain, storms, and temperature changes and summarize the patterns.",
      "turns": [
        "search <- rain storm",
        "search <- temperature cold warm",
        "search <- wind forecast",
        "search <- snow season",
        "search <- climate humidity",
        "search <- cloud sun",
        "calculator <- (72 - 32) * 5 / 9",
        "search <- storm wind rain",
        "search <- season climate",
        "reasoning only"
      ]
    },
    {
      "task_id": "SH-02",
      "profile": "search_heavy",
      "goal": "Put together a short overview of space topics: find what the corpus says about planets, the moon, eclipses, and telescopes.",
      "turns": [
        "search <- planet orbit",
        "search <- moon eclipse",
        "search <- solar eclipse",
        "search <- telescope star",
        "search <- rocket astronaut",
        "retrieve <- which planets can be seen without a telescope",
        "search <- mars earth",
        "search <- gravity light",
        "search <- galaxy star",
        "search <- orbit gravity",
        "reasoning only"
      ]
    },
    {
      "task_id": "CH-01",
      "profile": "code_heavy",
      "goal": "What is the sum of all prime numbers below 20000? Verify with a second computation and sanity-check the magnitude.",
      "turns": [
        "code_exec <- limit = 20000 sieve = [True] * limit sieve[0] = sieve[1] = False for i in range(2, int(limit ** 0.5)",
        "code_exec <- xs = [(i * 2654435761) % 100003 for i in range(30000)] xs.sort() result = xs[len(xs) // 2]",
        "calculator <- 21171191 / 1000000",
        "code_exec <- a, b = 0, 1 for _ in range(50000):     a, b = b, (a + b) % 1000000007 result = a",
        "reasoning only"
      ]
    },
    {
      "task_id": "CH-02",
      "profile": "code_heavy",
      "goal": "If I save 1000 dollars at 5 percent interest for 30 years, how much do I have? Also check a word-frequency count and a median.",
      "turns": [
        "code_exec <- balance = 1000.0 rate = 0.05 for year in range(30):     balanc
```

### `apu_characterization\out\tool_locality_ablation.json` size=42359
- keys: ['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'per_task', 'per_task_wall_cpu', 'session_rows', 'comparison', 'interpretation', 'reproduce_cmd', 'invariant']
  - `batch_wall_s`: float
  - `comparison`: list[dict] len=5
  - `comparison[].cpu_pct_wall_delta`: float
  - `comparison[].host_cpu_delta_ms`: float
  - `comparison[].io_pct_delta`: float
  - `comparison[].local_cpu_pct_wall`: float
  - `comparison[].local_host_cpu_ms`: float
  - `comparison[].local_io_pct`: float
  - `comparison[].local_search_calls`: int
  - `comparison[].local_tool_compute_ms`: float
  - `comparison[].remote_cpu_pct_wall`: float
  - `comparison[].remote_host_cpu_ms`: float
  - `comparison[].remote_io_pct`: float
  - `comparison[].remote_search_calls`: int
  - `comparison[].remote_tool_compute_ms`: float
  - `comparison[].task_id`: str
  - `comparison[].tool_compute_delta_ms`: float
  - `config`: dict
  - `config.backend`: str
  - `config.llm_median_scale`: float
  - `config.payload_note`: str
  - `config.payload_profile`: str
  - `config.retrieve_locality`: str
  - `config.seed`: int
  - `config.task_ids`: list[str] len=5
  - `config.tool_result_kb_max`: float
  - `env`: dict
  - `env.cores_logical`: int
  - `env.cores_physical`: int
  - `env.cpu_model`: str
  - `env.platform`: str
  - `env.python`: str
  - `env.ram_gb`: float
  - `experiment`: str
  - `generated_utc`: str
  - `git`: dict
  - `git.commit`: str
  - `git.dirty`: str
  - `interpretation`: str
  - `invariant`: dict
  - `invariant.instrumented_cpu_ns`: int
  - `invariant.limit`: float
  - `invariant.pass`: bool
  - `invariant.residual_cpu_ns`: int
  - `invariant.residual_fraction`: float
  - `invariant.total_thread_cpu_ns`: int
  - `per_task`: dict
  - `per_task.CH-02`: dict
  - `per_task.CH-02.amenable_broad_ns`: int
  - `per_task.CH-02.amenable_broad_share`: float
  - `per_task.CH-02.amenable_strict_ns`: int
  - `per_task.CH-02.amenable_strict_share`: float
  - `per_task.CH-02.categories`: dict
  - `per_task.CH-02.categories.GC`: dict
  - `per_task.CH-02.categories.GC.bytes_in`: int
  - `per_task.CH-02.categories.GC.bytes_out`: int
  - `per_task.CH-02.categories.GC.count`: int
  - `per_task.CH-02.categories.GC.cpu_ns`: int
  - `per_task.CH-02.categories.GC.wall_ns`: int
  - `per_task.CH-02.categories.HTTP_CLIENT`: dict
  - `per_task.CH-02.categories.HTTP_CLIENT.bytes_in`: int
  - `per_task.CH-02.categories.HTTP_CLIENT.bytes_out`: int
  - `per_task.CH-02.categories.HTTP_CLIENT.count`: int
  - `per_task.CH-02.categories.HTTP_CLIENT.cpu_ns`: int
  - `per_task.CH-02.categories.HTTP_CLIENT.wall_ns`: int
  - `per_task.CH-02.categories.ORCH_DISPATCH`: dict
  - `per_task.CH-02.categories.ORCH_DISPATCH.bytes_in`: int
  - `per_task.CH-02.categories.ORCH_DISPATCH.bytes_out`: int
  - `per_task.CH-02.categories.ORCH_DISPATCH.count`: int
  - `per_task.CH-02.categories.ORCH_DISPATCH.cpu_ns`: int
  - `per_task.CH-02.categories.ORCH_DISPATCH.wall_ns`: int
  - `per_task.CH-02.categories.ORCH_SETUP`: dict
  - `per_task.CH-02.categories.ORCH_SETUP.bytes_in`: int
  - `per_task.CH-02.categories.ORCH_SETUP.bytes_out`: int
  - `per_task.CH-02.categories.ORCH_SETUP.count`: int
  - `per_task.CH-02.categories.ORCH_SETUP.cpu_ns`: int
  - `per_task.CH-02.categories.ORCH_SETUP.wall_ns`: int
  - `per_task.CH-02.categories.PROMPT_ASSEMBLY`: dict
  - `per_task.CH-02.categories.PROMPT_ASSEMBLY.bytes_in`: int
  - `per_task.CH-02.categories.PROMPT_ASSEMBLY.bytes_out`: int
- `per_task` count: 5
```json
{
  "experiment": "tool_locality_ablation",
  "result_validity": "publishable",
  "generated_utc": "2026-07-07T17:38:38.200013+00:00",
  "setup_ref": {
    "setup_digest": "fe9707b03e17a5b7",
    "task_suite_digest": "a88a9e1058964219",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 325"
  },
  "git": {
    "commit": "unknown",
    "dirty": "unknown"
  },
  "env": {
    "python": "3.14.0",
    "platform": "Windows-11-10.0.26200-SP0",
    "cpu_model": "Intel64 Family 6 Model 204 Stepping 3, GenuineIntel",
    "cores_logical": 8,
    "cores_physical": 8,
    "ram_gb": 15.6
  },
  "config": {
    "backend": "openai",
    "seed": 0,
    "task_ids": [
      "SH-01",
      "SH-02",
      "CH-02",
      "RE-02",
      "RH-01"
    ],
    "retrieve_locality": "local",
    "llm_median_scale": 0.05,
    "payload_profile": "locality_ablation",
    "tool_result_kb_max": 4.0,
    "payload_note": "Synthetic tool-result padding capped at 4 KB so multi-tool OpenAI sessions stay under 128k context. Padding is identical across local/remote search arms."
  },
  "timer_overhead_ns_per_pair": 4843.75,
  "batch_wall_s": 80.80229739996139,
  "run": {
    "env": {},
    "config": {
      "profile": "tool_locality_ablation",
      "seed": 0,
      "mode": "sequential",
      "backend": "openai",
      "llm_median_scale": 0.05,
      "task_ids": [
        "SH-01",
        "SH-02",
        "CH-02",
        "RE-02",
        "RH-01"
      ],
      "retrieve_locality": "local",
      "total_cpu_basis": "process_time_all_threads"
    },
    "per_category": {
      "GC": {
        "cpu_ns": 93750000,
        "wall_ns": 93750000,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 81
      },
      "ORCH_SETUP": {
        "cpu_ns": 62500000,
        "wall_ns": 83644600,
        "bytes_in": 0,
        "bytes_out": 0,
        "count": 20
      },
      "PROMPT_ASSEMBLY": {
        "cpu_ns": 0,
        "wall_ns": 81300,
        "bytes_in": 0,
        "bytes_out": 85320,
        "count": 20
      },
      "TOKENIZATION": {
        "cpu_ns": 93750000,
        "wall_ns": 1923138100,
        "bytes_in": 180715,
        "bytes_out": 0,
        "count": 73
      },
      "SERIALIZATION": {
        "cpu_ns": 0,
        "wall_ns": 1790700,
        "bytes_in": 17236,
        "bytes_out": 162931,
        "count": 73
      },
      "HTTP_CLIENT": {
        "cpu_ns": 140625000,
        "wall_ns": 70794135100,
        "bytes_in": 18419,
        "bytes_out": 291,
        "count": 47
      },
     
```


## 7. Parquet / SQLite under apu_characterization

- `**/*.parquet`: 25
  - `apu_characterization\out\turntrace_v2\cpu_dryrun\corpus\call_records.parquet` size=16166
  - `apu_characterization\out\turntrace_v2\cpu_dryrun\corpus\trajectory_records.parquet` size=4066
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C2\corpus\call_records.parquet` size=14537
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C2\corpus\trajectory_records.parquet` size=4065
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C1\corpus\call_records.parquet` size=14544
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C1\corpus\trajectory_records.parquet` size=4065
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_b\corpus\call_records.parquet` size=18228
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_b\corpus\trajectory_records.parquet` size=4546
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_a\corpus\call_records.parquet` size=14699
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_a\corpus\trajectory_records.parquet` size=4162
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_b\corpus\call_records.parquet` size=18370
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_b\corpus\trajectory_records.parquet` size=4554
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_a\corpus\call_records.parquet` size=14728
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_a\corpus\trajectory_records.parquet` size=4162
  - `apu_characterization\out\turntrace_v2\cloud_c1_mock\corpus\call_records.parquet` size=14796
  - `apu_characterization\out\turntrace_v2\cloud_c1_mock\corpus\trajectory_records.parquet` size=4127
  - `apu_characterization\out\cap01\live_sources\cord-v2-test.parquet` size=234202795
  - `apu_characterization\out\cap01\live_sources\humanevalplus-hf\data\test-00000-of-00001-5973903632b82d40.parquet` size=2902210
  - `apu_characterization\out\cap01\live_sources\cord-v2-hf\data\test-00000-of-00001-9c204eb3f4e11791.parquet` size=234202795
  - `apu_characterization\out\cap01\live_sources\cord-v2-hf\data\train-00000-of-00004-b4aaeceff1d90ecb.parquet` size=490224630
- `**/*.sqlite`: 11
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\california_schools.sqlite` size=11116544
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\card_games.sqlite` size=261820416
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\codebase_community.sqlite` size=481419264
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\debit_card_specializing.sqlite` size=34635776
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\european_football_2.sqlite` size=597754880
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\financial.sqlite` size=71294976
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\formula_1.sqlite` size=22360064
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\student_club.sqlite` size=2641920
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\superhero.sqlite` size=237568
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\thrombosis_prediction.sqlite` size=7327744
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\toxicology.sqlite` size=2678784
- `**/*.db`: 0