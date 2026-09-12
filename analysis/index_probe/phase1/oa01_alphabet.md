# OA-01 Alphabet Recovery (Phase A)

## 1. `.traj.json` schema

Found **16** `*.traj.json` files under `out/oa01/runs/`.

Example file: `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\subject\pydata__xarray-3364\pydata__xarray-3364.traj.json`

### Top-level schema

```
trajectory_format: 'mini-swe-agent-1.1'
instance_id: 'pydata__xarray-3364'
keys: ['info', 'instance_id', 'messages', 'trajectory_format']
info.keys: ['config', 'exit_status', 'mini_version', 'model_stats', 'submission']
messages: list len=64 roles={'system': 1, 'user': 1, 'assistant': 28, 'tool': 33, 'exit': 1}
assistant message keys: ['annotations', 'content', 'extra', 'function_call', 'provider_specific_fields', 'role', 'tool_calls']
tool_calls[0] keys: ['function', 'id', 'type']
tool_calls[0].function keys: ['arguments', 'name']
```

### Three sample assistant messages (verbatim bash commands)

#### Sample from `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\subject\pydata__xarray-3364\pydata__xarray-3364.traj.json`
Content (truncated to 800 chars):
```
THOUGHT:

The PR description concerns the behavior of concatenating xarray Datasets (likely in a function called `concat`) to "ignore missing variables when concatenating datasets", more like pandas' `pd.concat` with an outer join on columns. Currently, `concat` requires all datasets to have the same variables, or the user must create dummy variables with NaN—which is inconvenient.

Task:

- Find the code that handles Dataset concatenation.
- Confirm how it currently handles variable mismatches.
- Plan where to introduce an option to ignore missing variables, filling them with NaNs (by analogy to `pd.concat(..., join="outer")`).
- See how options are provided to `concat`.

Plan:

1. Locate the file(s) implementing `concat` for Datasets.
2. Inspect the existing logic, especially variable al
```
tool_calls / commands:
```json
[
  {
    "name": "bash",
    "arguments": {
      "command": "ls -l"
    }
  },
  {
    "name": "bash",
    "arguments": {
      "command": "grep -R 'def concat' ."
    }
  },
  {
    "name": "bash",
    "arguments": {
      "command": "grep -Ri 'class Dataset' ."
    }
  },
  {
    "name": "bash",
    "arguments": {
      "command": "grep -Ri 'join' ."
    }
  }
]
```

#### Sample from `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\subject\pydata__xarray-3364\pydata__xarray-3364.traj.json`
Content (truncated to 800 chars):
```
THOUGHT:

From the grep results:
- The main concat function is in `xarray/core/concat.py`: `def concat(...`
- There is also a class method `def concat` for Variable in `xarray/core/variable.py`, but the higher-level dataset logic should be in `xarray/core/concat.py`.
- In `xarray/core/concat.py`, several lines indicate a `join` argument is already present, with default `"outer"`, and `join` passed to different subfunctions.
- The Dataset class is implemented in `xarray/core/dataset.py`, but concat logic is likely in `concat.py`.

Next Steps:

1. Inspect the first ~50 lines of `xarray/core/concat.py` to see docstring, function signature, and where/if handling of variables (and join logic) occurs.
2. Look for comments or code about variable alignment, missing variables, and how join is handl
```
tool_calls / commands:
```json
[
  {
    "name": "bash",
    "arguments": {
      "command": "head -50 xarray/core/concat.py"
    }
  }
]
```

#### Sample from `apu_characterization\out\oa01\runs\OA01-M-03-pydata__xarray-3364\subject\pydata__xarray-3364\pydata__xarray-3364.traj.json`
Content (truncated to 800 chars):
```
THOUGHT:

The docstring for `concat` in `xarray/core/concat.py` shows that it already has a `join` parameter (default "outer"); this matches the intended "outer join" semantics described in the PR. However, the PR suggests that, currently, concat does not handle missing variables by automatically adding NaN-filled versions (and that the user must do this by hand), whereas pandas does this for dataframe columns.

This implies that, internally, xarray's `concat` does not create NaN-filled variables for missing data_vars/coords in some datasets—likely raising errors or simply dropping those variables. 

Next, I need to see:
- How `join` is actually handled for missing variables (not just coordinates/indices).
- Where the actual variable alignment happens.
- If there is code that raises or ign
```
tool_calls / commands:
```json
[
  {
    "name": "bash",
    "arguments": {
      "command": "grep -n 'raise' xarray/core/concat.py"
    }
  },
  {
    "name": "bash",
    "arguments": {
      "command": "grep -n 'missing' xarray/core/concat.py"
    }
  },
  {
    "name": "bash",
    "arguments": {
      "command": "grep -n 'concat_vars' xarray/core/concat.py"
    }
  }
]
```

## 2. Join to `derived/turn_records.jsonl`

- OA01 run dirs: 18
- turn_records rows: 335
- **traj-primary join** (assistant[i] present and usable): 266/335 (79.4%)
- **final join_ok** (traj OR api_boundary fallback): 335/335 (100.0%)
- hard join failures (neither source): 0
- recovery source counts:
  - `traj`: 266
  - `api_boundary`: 69
- runs with no usable `.traj.json` path/content: ['OA01-M-10-matplotlib__matplotlib-25433']
  - note: `OA01-M-10-matplotlib__matplotlib-25433` has `subject/` but no `.traj.json` (only `minisweagent.log`); commands recovered from `api_boundary.jsonl`.
- assistant/turn_record count mismatches (traj truncated vs API turns):
  - OA01-M-05-django__django-13925: assistants=9 turn_records=10
  - OA01-M-06-sphinx-doc__sphinx-8435: assistants=23 turn_records=24
  - OA01-M-07-mwaskom__seaborn-3407: assistants=12 turn_records=15
  - OA01-M-11-scikit-learn__scikit-learn-25638: assistants=25 turn_records=29
  - OA01-M-14-sympy__sympy-24152: assistants=6 turn_records=7
  - OA01-P-00-pallets__flask-4992: assistants=17 turn_records=18
  - OA01-P-02-django__django-13590: assistants=10 turn_records=11
  - OA01-S-00-pallets__flask-4992-attempt02: assistants=0 turn_records=3
  - OA01-S-00-pallets__flask-4992-attempt03: assistants=0 turn_records=3
  - typical cause: final `submit` / `reason_or_finalize` turns present in `turn_records` + `api_boundary` but missing from the subject `.traj.json`.
- join notes (top):
  - `no_traj_json; recovered_via_api_boundary`: 51
  - `traj_has_zero_assistant_messages; recovered_via_api_boundary`: 6
  - `fanout_mismatch src=1 record=2`: 3
  - `turn_index 9 out of range for 9 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 23 out of range for 23 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 12 out of range for 12 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 13 out of range for 12 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 14 out of range for 12 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 25 out of range for 25 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 26 out of range for 25 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 27 out of range for 25 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 28 out of range for 25 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 6 out of range for 6 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 17 out of range for 17 assistant msgs; recovered_via_api_boundary`: 1
  - `turn_index 10 out of range for 10 assistant msgs; recovered_via_api_boundary`: 1
- fanout mismatches (recovered calls ≠ record tool_names len): 3

### Fanout distribution (calls per joined turn; 0 = ANSWER)

| calls/turn | count |
|---:|---:|
| 0 | 8 |
| 1 | 300 |
| 2 | 10 |
| 3 | 12 |
| 4 | 5 |

## 3. Verb alphabet

Normalization: take FIRST verb of each bash invocation; for pipes/`&&`/`||`/`;` chains record `chain_length` separately. Strip flags/args via first-token only. Aliases: `rg→grep`, `python3→python`, `python -m pytest→pytest`, `complete_task_and_submit_final_output→submit`.

- total call-level symbols (incl. ANSWER turns): **384**
- distinct verbs: **15**
- OTHER: **1** (0.3%)

### Frequency distribution

| verb | count | pct |
|---|---:|---:|
| `grep` | 92 | 24.0% |
| `awk` | 83 | 21.6% |
| `head` | 62 | 16.1% |
| `sed` | 36 | 9.4% |
| `cat` | 27 | 7.0% |
| `ls` | 22 | 5.7% |
| `submit` | 21 | 5.5% |
| `git` | 17 | 4.4% |
| `cp` | 10 | 2.6% |
| `ANSWER` | 8 | 2.1% |
| `find` | 2 | 0.5% |
| `OTHER` | 1 | 0.3% |
| `rm` | 1 | 0.3% |
| `tail` | 1 | 0.3% |
| `diff` | 1 | 0.3% |

### Chain length distribution

| chain_length | count |
|---:|---:|
| 1 | 276 |
| 2 | 89 |
| 3 | 8 |
| 4 | 1 |
| 6 | 1 |
| 11 | 1 |

### Top unmatched OTHER commands (for normalizer extension)

| raw first token | count | example command |
|---|---:|---|
| `nano` | 1 | `nano xarray/core/concat.py` |

OTHER is 0.3% (≤15%). Top unmatched listed for transparency.


### First-call-per-turn distribution (issue-width target a)

| verb | turns | pct |
|---|---:|---:|
| `awk` | 77 | 23.0% |
| `head` | 60 | 17.9% |
| `grep` | 56 | 16.7% |
| `sed` | 35 | 10.4% |
| `cat` | 25 | 7.5% |
| `submit` | 21 | 6.3% |
| `ls` | 20 | 6.0% |
| `git` | 17 | 5.1% |
| `cp` | 10 | 3.0% |
| `ANSWER` | 8 | 2.4% |
| `find` | 2 | 0.6% |
| `OTHER` | 1 | 0.3% |
| `rm` | 1 | 0.3% |
| `tail` | 1 | 0.3% |
| `diff` | 1 | 0.3% |

## 4. Cross-check vs `step_type_semantic`

Agreement rule (coarse family match): when atom count equals call count, zip-match each atom's verb family; otherwise require a majority of verbs in the union family. Families: inspect→{ls,grep,cat,head,tail,sed,awk,…}, edit→{sed,patch,echo,cp,…}, verify→{pytest,…}, submit→{submit}, reason_or_finalize→ANSWER. `shell_other` soft-agrees.

- agreement: **201/335** (60.0%)
- breakdown:
  - `family:miss`: 125
  - `family:ok`: 187
  - `reason_or_finalize:miss`: 9
  - `reason_or_finalize:ok`: 8
  - `shell_other_or_unknown:ok`: 6

**Interpretation:** low family agreement is expected and informative. `step_type_semantic` (from `derive._command_semantic`) labels *intent* (e.g. edit via `cat > file <<EOF`, or submit via `echo COMPLETE_TASK… && cat patch.txt`), while the verb alphabet labels *surface command*. These are complementary, not duplicates. Submit turns are normalized to `submit` when the command contains `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.

Disagreement examples (pre-submit-normalization style / family misses):
- OA01-M-03-pydata__xarray-3364 t19: semantic=edit verbs=['head'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['head -340 xarray/core/concat.py > head.tmp; tail -46 xarray/core/concat.py > tail.tmp']
- OA01-M-03-pydata__xarray-3364 t20: semantic=edit verbs=['cat'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['cat concat_window_editable.txt | sed \'s/try:/# PATCHED: variable join outer patch\\n            vars = []\\n            missing_variable = False\\n            example_var = None\\n            for i, ds in enumerate(datasets):\\n                if k in ds.variables:\\n                    v = ds.variables[k]\\n                    vars.append(v)\\n                    example_var = v if example_var is None else example_var\\n                else:\\n                    missing_variable = True\\n                    # create NaN variable with correct dims/shape\\n                    # Use dims and dtype from example_var or fallback\\n                    if example_var is not None:\\n                        dims = example_var.dims\\n                        shape = tuple(dims_sizes[d] for d in dims)\\n                        fill = fill_value\\n                        dtype = getattr(example_var._data, "dtype", float)\\n                    else:\\n                        # fallback: concat_dim & single-dim, float\\n                        dims = (dim,)\\n                        shape = (concat_dim_lengths[i],)\\n                        fill = fill_value\\n                        dtype = float\\n                    data = np.full(shape, fill, dtype=dtype)\\n                    v = Variable(dims, data)\\n                    vars.append(v)\\n            if missing_variable:\\n                if join != "outer":\\n                    raise ValueError("%r is not present in all datasets." % k)\\n            vars = ensure_common_dims(vars)\' | sed \'/except KeyError:/d\' | sed \'/raise ValueError("%r is not present in all datasets." % k)/d\' > patch_body.tmp']
- OA01-M-03-pydata__xarray-3364 t21: semantic=edit verbs=['cat'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['cat > concat_patch_block.tmp <<\'EOF\'\n    # stack up each variable to fill-out the dataset (in order)\n    # n.b. this loop preserves variable order, needed for groupby.\n    for k in datasets[0].variables:\n        if k in concat_over:\n            # PATCHED: allow missing variables for join="outer"\n            vars = []\n            missing_variable = False\n            example_var = None\n            for i, ds in enumerate(datasets):\n                if k in ds.variables:\n                    v = ds.variables[k]\n                    vars.append(v)\n                    example_var = v if example_var is None else example_var\n                else:\n                    missing_variable = True\n                    # create NaN variable with correct dims/shape\n                    # Use dims and dtype from example_var or fallback\n                    if example_var is not None:\n                        dims = example_var.dims\n                        shape = tuple(dims_sizes[d] for d in dims)\n                        fill = fill_value\n                        dtype = getattr(example_var._data, "dtype", float)\n                    else:\n                        # fallback: concat_dim & single-dim, float\n                        dims = (dim,)\n                        shape = (concat_dim_lengths[i],)\n                        fill = fill_value\n                        dtype = float\n                    data = np.full(shape, fill, dtype=dtype)\n                    v = Variable(dims, data)\n                    vars.append(v)\n            if missing_variable:\n                if join != "outer":\n                    raise ValueError("%r is not present in all datasets." % k)\n            vars = ensure_common_dims(vars)\n            combined = concat_vars(vars, dim, positions)\n            assert isinstance(combined, Variable)\n            result_vars[k] = combined\n\nEOF']
- OA01-M-03-pydata__xarray-3364 t22: semantic=edit verbs=['cat'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['cat head.tmp concat_patch_block.tmp tail.tmp > xarray/core/concat.py']
- OA01-M-03-pydata__xarray-3364 t23: semantic=inspect verbs=['rm'] expected⊃['awk', 'cat', 'diff', 'find', 'grep', 'head', 'ls', 'pwd'] cmds=['rm head.tmp tail.tmp concat_patch_block.tmp concat_edit_window.txt concat_window_editable.txt']
- OA01-M-03-pydata__xarray-3364 t24: semantic=edit verbs=['git'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['git diff -- xarray/core/concat.py > patch.txt']
- OA01-M-03-pydata__xarray-3364 t25: semantic=edit verbs=['head'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['head -40 patch.txt']
- OA01-M-03-pydata__xarray-3364 t26: semantic=edit verbs=['tail'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['tail -40 patch.txt']
- OA01-M-04-matplotlib__matplotlib-25332 t1: semantic=edit+edit+inspect verbs=['awk', 'awk', 'grep'] expected⊃['apply_patch', 'awk', 'cat', 'cp', 'diff', 'echo', 'find', 'grep'] cmds=["awk 'NR>=1400&&NR<=1500' /testbed/lib/matplotlib/figure.py", "awk 'NR>=3190&&NR<=3220' /testbed/lib/matplotlib/figure.py"]
- OA01-M-04-matplotlib__matplotlib-25332 t3: semantic=edit verbs=['awk'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=["awk 'NR>=180&&NR<=200' /testbed/lib/matplotlib/figure.py"]
- OA01-M-04-matplotlib__matplotlib-25332 t6: semantic=edit verbs=['awk'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=["awk 'NR>=750&&NR<=860' /testbed/lib/matplotlib/cbook.py"]
- OA01-M-04-matplotlib__matplotlib-25332 t8: semantic=edit verbs=['git'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['git diff -- /testbed/lib/matplotlib/figure.py > patch.txt']
- OA01-M-04-matplotlib__matplotlib-25332 t9: semantic=edit verbs=['head'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['head -40 patch.txt']
- OA01-M-05-django__django-13925 t6: semantic=edit verbs=['git'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['git diff --exit-code > patch.txt']
- OA01-M-05-django__django-13925 t7: semantic=edit verbs=['cat'] expected⊃['apply_patch', 'cp', 'echo', 'mkdir', 'mv', 'patch', 'perl', 'python'] cmds=['cat patch.txt']

---
Wrote join table: `analysis\index_probe\phase1\oa01_verb_turns.jsonl`

**STOP — Phase A complete. Await alphabet review before Phase B.**
