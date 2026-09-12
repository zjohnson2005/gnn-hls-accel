# Phase 0 Inventory Supplement

## TurnTrace .ttbundle format probe

### `apu_characterization\out\turntrace_v2\_gate_smoke\replay\bundles\syn-000.ttbundle` size=881
- magic hex: 78dadd57db6edb3810fd1543cfd98277
- magic ascii-ish: b'x\xda\xddW\xdbn\xdb8\x10\xfd\x15C\xcf\xd9\x82w'
- not zip: BadZipFile: File is not a zip file
- not tar: ReadError: file could not be opened successfully:
- method gz: ReadError('not a gzip file')
- method bz2: ReadError('not a bzip2 file')
- method xz: ReadError('not an lzma file')
- method zst: ReadError('not a zstd file')
- method tar: ReadError('invalid header')
- not gzip: BadGzipFile
- zlib decompress ok, first32=b'{"deployment_id":"L1b","harness_'
  json type=dict
- not msgpack / no msgpack: ModuleNotFoundError: No module named 'msgpack'
- u32le[0]=1474157176 u32le[1]=953904859
- u32be[0]=2027609431
### `apu_characterization\out\turntrace_v2\_gate_smoke\replay\bundles\syn-001.ttbundle` size=882
- magic hex: 78dadd57db6edb3810fd1543cfd98277
- magic ascii-ish: b'x\xda\xddW\xdbn\xdb8\x10\xfd\x15C\xcf\xd9\x82w'
- not zip: BadZipFile: File is not a zip file
- not tar: ReadError: file could not be opened successfully:
- method gz: ReadError('not a gzip file')
- method bz2: ReadError('not a bzip2 file')
- method xz: ReadError('not an lzma file')
- method zst: ReadError('not a zstd file')
- method tar: ReadError('invalid header')
- not gzip: BadGzipFile
- zlib decompress ok, first32=b'{"deployment_id":"L1b","harness_'
  json type=dict
- not msgpack / no msgpack: ModuleNotFoundError: No module named 'msgpack'
- u32le[0]=1474157176 u32le[1]=953904859
- u32be[0]=2027609431
### `apu_characterization\out\turntrace_v2\_gate_smoke\replay\bundles\syn-002.ttbundle` size=882
- magic hex: 78dadd57db6edb3810fd1543cfd98277
- magic ascii-ish: b'x\xda\xddW\xdbn\xdb8\x10\xfd\x15C\xcf\xd9\x82w'
- not zip: BadZipFile: File is not a zip file
- not tar: ReadError: file could not be opened successfully:
- method gz: ReadError('not a gzip file')
- method bz2: ReadError('not a bzip2 file')
- method xz: ReadError('not an lzma file')
- method zst: ReadError('not a zstd file')
- method tar: ReadError('invalid header')
- not gzip: BadGzipFile
- zlib decompress ok, first32=b'{"deployment_id":"L1b","harness_'
  json type=dict
- not msgpack / no msgpack: ModuleNotFoundError: No module named 'msgpack'
- u32le[0]=1474157176 u32le[1]=953904859
- u32be[0]=2027609431
### `apu_characterization\out\turntrace_v2\rev_c_cp2\class_i\bundles\CPU0-raw_python-TT-RET-s0-cache_only-orchestration_optimized.ttbundle` size=175870
- magic hex: 78daec7d0b731b37b2f55f992b57ed52
- magic ascii-ish: b'x\xda\xec}\x0bs\x1b7\xb2\xf5_\x99+W\xedR'
- not zip: BadZipFile: File is not a zip file
- not tar: ReadError: file could not be opened successfully:
- method gz: ReadError('not a gzip file')
- method bz2: ReadError('not a bzip2 file')
- method xz: ReadError('not an lzma file')
- method zst: ReadError('not a zstd file')
- method tar: ReadError('invalid header')
- not gzip: BadGzipFile
- zlib decompress ok, first32=b'{"deployment_id":"CPU0","harness'
  json type=dict
- not msgpack / no msgpack: ModuleNotFoundError: No module named 'msgpack'
- u32le[0]=2112674424 u32le[1]=924545803
- u32be[0]=2027613309

## Code references to ttbundle writer

- `apu_characterization\turntrace_v2\collect_cloud.py`
- `apu_characterization\turntrace_v2\collect_full.py`
- `apu_characterization\turntrace_v2\collect_rev_c.py`
- `apu_characterization\turntrace_v2\runner.py`
- `apu_characterization\turntrace_v2\smoke_live.py`
- `apu_characterization\turntrace_v2\workload\toy_agent.py`
- `apu_characterization\tests\turntrace_v2\test_derive.py`
- `apu_characterization\tests\turntrace_v2\test_replay.py`
- `apu_characterization\tests\turntrace_v2\test_rev_c.py`

## TurnTrace events.json aggregate

Total event files: 93

### area `cloud_c1_mock` files=4
- distinct trajectories (file/field): 4
- turns/file min/med/max: 4/4.0/4
- total_turns: 16
- empty_tool_turns: 0
- multi_tool_turns: 2
- tool alphabet size: 4
- top tools: [('grep', 6), ('read_file', 4), ('edit_file', 4), ('run_tests', 4)]

### area `cloud_full` files=40
- distinct trajectories (file/field): 36
- turns/file min/med/max: 4/4.0/4
- total_turns: 160
- empty_tool_turns: 0
- multi_tool_turns: 20
- tool alphabet size: 4
- top tools: [('grep', 60), ('read_file', 40), ('edit_file', 40), ('run_tests', 40)]

### area `cloud_smoke` files=2
- distinct trajectories (file/field): 2
- turns/file min/med/max: 4/4.0/4
- total_turns: 8
- empty_tool_turns: 0
- multi_tool_turns: 0
- tool alphabet size: 4
- top tools: [('read_file', 2), ('edit_file', 2), ('run_tests', 2), ('grep', 2)]

### area `cpu_dryrun` files=5
- distinct trajectories (file/field): 5
- turns/file min/med/max: 6/6/6
- total_turns: 30
- empty_tool_turns: 0
- multi_tool_turns: 0
- tool alphabet size: 3
- top tools: [('read_file', 10), ('edit_file', 10), ('run_tests', 10)]

### area `rev_c_cp2` files=42
- distinct trajectories (file/field): 42
- turns/file min/med/max: 18/20.0/20
- total_turns: 836
- empty_tool_turns: 0
- multi_tool_turns: 0
- tool alphabet size: 6
- top tools: [('read_file', 280), ('edit_file', 280), ('run_tests', 240), ('search', 12), ('fetch', 12), ('append_summary', 12)]

## OA-01 tool alphabet / decision points

- trajectories with turn_records: 17
- turns/traj min/med/max: 3/15/51
- is_tool_call: {True: 318, False: 17}
- status: {'ok': 334, 'error': 1}
- step_type_semantic top: [('edit', 143), ('inspect', 128), ('reason_or_finalize', 17), ('submit', 14), ('inspect+inspect+inspect', 10), ('inspect+inspect', 9), ('shell_other', 6), ('inspect+inspect+inspect+inspect', 5), ('edit+edit+inspect', 1), ('edit+edit', 1), ('edit+edit+edit', 1)]
- tool summary counters: [('occ:bash', 367), ('bash', 291), ('bash+...', 27), ('__NO_TOOL__/ANSWER', 17)]

## OA-01 exec_events.jsonl schema

### `apu_characterization\out\oa01\runs\OA01-S-00-pallets__flask-4992-attempt03\raw\exec_events.jsonl` records=4
- keys: ['argv', 'command', 'container_id', 'docker_operation', 'event', 'schema_version', 'span_id', 'trajectory_id', 'unix_ns']
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-2c1f05bb",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pallets_1776_flask-4992:latest",
    "sleep",
    "2h"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "run",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-66c5e4c1c5b341a69c75d6232ddc0c88",
  "trajectory_id": "OA01-S-00-pallets__flask-4992-attempt03",
  "unix_ns": 1784224911168143039
}
```
```json
{
  "argv": [
    "run",
    "-d",
    "--name",
    "minisweagent-2c1f05bb",
    "-w",
    "/testbed",
    "--rm",
    "docker.io/swebench/sweb.eval.x86_64.pallets_1776_flask-4992:latest",
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
  "span_id": "exec-66c5e4c1c5b341a69c75d6232ddc0c88",
  "stdout_stderr_path": "/mnt/c/Users/zjohn/Projects/gnn-hls-accel/apu_characterization/out/oa01/runs/OA01-S-00-pallets__flask-4992-attempt03/raw/tool_io/exec-66c5e4c1c5b341a69c75d6232ddc0c88.stdout_stderr.bin",
  "trajectory_id": "OA01-S-00-pallets__flask-4992-attempt03",
  "unix_ns": 1784224911460778091
}
```
```json
{
  "argv": [
    "stop",
    "646e9ec077cabcf7d42b5dd87454af72c1c01c914c5b6762deb27ff4062d9aac"
  ],
  "command": null,
  "container_id": null,
  "docker_operation": "stop",
  "event": "start",
  "schema_version": "oa01_exec_event_v1",
  "span_id": "exec-4fa85f1107be4370b2cf44b7cce6ca1a",
  "trajectory_id": "OA01-S-00-pallets__flask-4992-attempt03",
  "unix_ns": 1784224924412126643
}
```

## CAP-01 BFCL multi_turn (JSONL-masquerading-as-.json)


### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_base.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 1/4.0/7
- top-level keys: ['excluded_function', 'id', 'initial_config', 'involved_classes', 'path', 'question']
#### sample[0]
```json
{
  "id": "multi_turn_base_0",
  "question": [
    [
      {
        "role": "user",
        "content": "Move 'final_report.pdf' within document directory to 'temp' directory in document. Make sure to create the directory"
      }
    ],
    [
      {
        "role": "user",
        "content": "Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension."
      }
    ],
    [
      {
        "role": "user",
        "content": "Move 'previous_report.pdf' in document directory to temp as well and having final report also there, proceed to juxtapose it with 'previous_report.pdf' to detect any critical alterations."
      }
    ]
  ],
  "initial_config": "{\"GorillaFileSystem\": {\"root\": {\"workspace\": {\"type\": \"directory\", \"contents\": {\"document\": {\"type\": \"directory\", \"contents\": {\"final_report.pdf\": {\"type\": \"file\", \"content\": \"Year2024 This is the final report content including budget analysis and other sections.\"}, \"previous_report.pdf\": {\"type\": \"file\", \"content\": \"Year203 This is the previous report content with different budget analysis.\"}}}, \"archive\": {\"type\": \"directory\", \"contents\": {}}}}}}, \"TwitterAPI\": {\"tweet_counter\": 3, \"tweets\": {\"0\": {\"id\": 0, \"username\": \"analyst_pro\", \"content\": \"Just finished analyzing the reports!\", \"tags\": [\"#analysis\", \"#reports\"], \"mentions\": []}, \"1\": {\"id\": 1, \"username\": \"analyst_pro\", \"content\": \"Budget analysis insights coming soon!\", \"tags\": [\"#budget\", \"#analysis\", \"#insights\"], \"mentions\": []...<truncated>",
  "path": [
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.sort",
    "GorillaFileSystem.diff",
    "TwitterAPI.post_tweet"
  ],
  "involved_classes": [
    "TwitterAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_base_1",
  "question": [
    [
      {
        "role": "user",
        "content": "I am alex. Check if the current directory is under my name and list all the visible and hidden contents in the current directory now, please."
      }
    ],
    [
      {
        "role": "user",
        "content": "Go to workspace directory and move one of the 'log.txt' files into a new directory 'archive'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Investigate within 'log.txt' for the occurrence of the keyword 'Error'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Finally, show the last 20 lines the file."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "alex": {
          "type": "directory",
          "contents": {
            "workspace": {
              "type": "directory",
              "contents": {
                "log.txt": {
                  "type": "file",
                  "content": "This is a log file. No errors found. Another line. Yet another line. Error: Something went wrong. Final line."
                },
                "archive": {
                  "type": "directory",
                  "contents": {}
                },
                ".hidden_file": {
                  "type": "file",
                  "content": "This is a hidden file."
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.ls",
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.tail"
  ],
  "involved_classes": [
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_base_2",
  "question": "[[{\"role\": \"user\", \"content\": \"Go into document folder and Could you draft up a create a document titled 'TeamNotes.txt' for keeping track of all the fresh ideas?\"}], [{\"role\": \"user\", \"content\": \"We've gathered a couple of wise insights from Simona, so could you jot down 'Collaboration leads to success. Innovation ignites growth.' into the previous file?\"}], [{\"role\": \"user\", \"content\": \"There seems to be some differences noted by Simona between the 'ideas.txt' file and our 'TeamNotes.txt'. Could you delve into these files to identify and explain the line-by-line distinctions for her?\"}], [{\"role\": \"user\", \"content\": \"Simona thinks it's a smart move to secure 'TeamNotes.txt'. How about we copy it over to the archive directory under the name IdeasArchive.txt while keeping the original inta...<truncated>",
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "simona": {
          "type": "directory",
          "contents": {
            "documents": {
              "type": "directory",
              "contents": {
                "ideas.txt": {
                  "type": "file",
                  "content": "Collaboration leads to success. Innovation ignites growth."
                },
                "Archived": {
                  "type": "directory",
                  "contents": {}
                },
                "past_projects": {
                  "type": "directory",
                  "contents": {}
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.touch",
    "GorillaFileSystem.echo",
    "GorillaFileSystem.diff",
    "GorillaFileSystem.cp",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.cat",
    "TicketAPI.close_ticket"
  ],
  "involved_classes": [
    "TicketAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "rm"
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_long_context.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 1/4.0/7
- top-level keys: ['excluded_function', 'id', 'initial_config', 'involved_classes', 'path', 'question']
#### sample[0]
```json
{
  "id": "multi_turn_long_context_0",
  "question": [
    [
      {
        "role": "user",
        "content": "Move 'final_report.pdf' within document directory to 'temp' directory in document. Make sure to create the directory"
      }
    ],
    [
      {
        "role": "user",
        "content": "Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension."
      }
    ],
    [
      {
        "role": "user",
        "content": "Move 'previous_report.pdf' in document directory to temp as well and having final report also there, proceed to juxtapose it with 'previous_report.pdf' to detect any critical alterations."
      }
    ]
  ],
  "initial_config": "{\"GorillaFileSystem\": {\"root\": {\"workspace\": {\"type\": \"directory\", \"contents\": {\"document\": {\"type\": \"directory\", \"contents\": {\"final_report.pdf\": {\"type\": \"file\", \"content\": \"Year2024 This is the final report content including budget analysis and other sections.\"}, \"previous_report.pdf\": {\"type\": \"file\", \"content\": \"Year203 This is the previous report content with different budget analysis.\"}}}, \"archive\": {\"type\": \"directory\", \"contents\": {}}}}}}, \"TwitterAPI\": {\"tweet_counter\": 3, \"tweets\": {\"0\": {\"id\": 0, \"username\": \"analyst_pro\", \"content\": \"Just finished analyzing the reports!\", \"tags\": [\"#analysis\", \"#reports\"], \"mentions\": []}, \"1\": {\"id\": 1, \"username\": \"analyst_pro\", \"content\": \"Budget analysis insights coming soon!\", \"tags\": [\"#budget\", \"#analysis\", \"#insights\"], \"mentions\": []...<truncated>",
  "path": [
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.sort",
    "GorillaFileSystem.diff",
    "TwitterAPI.post_tweet"
  ],
  "involved_classes": [
    "TwitterAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_long_context_1",
  "question": [
    [
      {
        "role": "user",
        "content": "I am alex. Check if the current directory is under my name and list all the visible and hidden contents in the current directory now, please."
      }
    ],
    [
      {
        "role": "user",
        "content": "Go to workspace directory and move one of the 'log.txt' files into a new directory 'archive'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Investigate within 'log.txt' for the occurrence of the keyword 'Error'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Finally, show the last 20 lines the file."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "alex": {
          "type": "directory",
          "contents": {
            "workspace": {
              "type": "directory",
              "contents": {
                "log.txt": {
                  "type": "file",
                  "content": "This is a log file. No errors found. Another line. Yet another line. Error: Something went wrong. Final line."
                },
                "archive": {
                  "type": "directory",
                  "contents": {}
                },
                ".hidden_file": {
                  "type": "file",
                  "content": "This is a hidden file."
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.ls",
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.tail"
  ],
  "involved_classes": [
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_long_context_2",
  "question": "[[{\"role\": \"user\", \"content\": \"Go into document folder and Could you draft up a create a document titled 'TeamNotes.txt' for keeping track of all the fresh ideas?\"}], [{\"role\": \"user\", \"content\": \"We've gathered a couple of wise insights from Simona, so could you jot down 'Collaboration leads to success. Innovation ignites growth.' into the previous file?\"}], [{\"role\": \"user\", \"content\": \"There seems to be some differences noted by Simona between the 'ideas.txt' file and our 'TeamNotes.txt'. Could you delve into these files to identify and explain the line-by-line distinctions for her?\"}], [{\"role\": \"user\", \"content\": \"Simona thinks it's a smart move to secure 'TeamNotes.txt'. How about we copy it over to the archive directory under the name IdeasArchive.txt while keeping the original inta...<truncated>",
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "simona": {
          "type": "directory",
          "contents": {
            "documents": {
              "type": "directory",
              "contents": {
                "ideas.txt": {
                  "type": "file",
                  "content": "Collaboration leads to success. Innovation ignites growth."
                },
                "Archived": {
                  "type": "directory",
                  "contents": {}
                },
                "past_projects": {
                  "type": "directory",
                  "contents": {}
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.touch",
    "GorillaFileSystem.echo",
    "GorillaFileSystem.diff",
    "GorillaFileSystem.cp",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.cat",
    "TicketAPI.close_ticket"
  ],
  "involved_classes": [
    "TicketAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "rm"
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_func.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/5.0/8
- top-level keys: ['excluded_function', 'id', 'initial_config', 'involved_classes', 'missed_function', 'path', 'question']
#### sample[0]
```json
{
  "id": "multi_turn_miss_func_0",
  "question": [
    [
      {
        "role": "user",
        "content": "Move 'final_report.pdf' within document directory to 'temp' directory in document. Make sure to create the directory"
      }
    ],
    [
      {
        "role": "user",
        "content": "Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension."
      }
    ],
    [],
    [
      {
        "role": "user",
        "content": "Move 'previous_report.pdf' in document directory to temp as well and having final report also there, proceed to juxtapose it with 'previous_report.pdf' to detect any critical alterations."
      }
    ]
  ],
  "initial_config": "{\"GorillaFileSystem\": {\"root\": {\"workspace\": {\"type\": \"directory\", \"contents\": {\"document\": {\"type\": \"directory\", \"contents\": {\"final_report.pdf\": {\"type\": \"file\", \"content\": \"Year2024 This is the final report content including budget analysis and other sections.\"}, \"previous_report.pdf\": {\"type\": \"file\", \"content\": \"Year203 This is the previous report content with different budget analysis.\"}}}, \"archive\": {\"type\": \"directory\", \"contents\": {}}}}}}, \"TwitterAPI\": {\"tweet_counter\": 3, \"tweets\": {\"0\": {\"id\": 0, \"username\": \"analyst_pro\", \"content\": \"Just finished analyzing the reports!\", \"tags\": [\"#analysis\", \"#reports\"], \"mentions\": []}, \"1\": {\"id\": 1, \"username\": \"analyst_pro\", \"content\": \"Budget analysis insights coming soon!\", \"tags\": [\"#budget\", \"#analysis\", \"#insights\"], \"mentions\": []...<truncated>",
  "path": [
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.sort",
    "GorillaFileSystem.diff",
    "TwitterAPI.post_tweet"
  ],
  "involved_classes": [
    "TwitterAPI",
    "GorillaFileSystem"
  ],
  "missed_function": {
    "3": [
      "sort"
    ]
  },
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_miss_func_1",
  "question": [
    [
      {
        "role": "user",
        "content": "I am alex. Check if the current directory is under my name and list all the visible and hidden contents in the current directory now, please."
      }
    ],
    [
      {
        "role": "user",
        "content": "Go to workspace directory and move one of the 'log.txt' files into a new directory 'archive'."
      }
    ],
    [],
    [
      {
        "role": "user",
        "content": "Investigate within 'log.txt' for the occurrence of the keyword 'Error'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Finally, show the last 20 lines the file."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "alex": {
          "type": "directory",
          "contents": {
            "workspace": {
              "type": "directory",
              "contents": {
                "log.txt": {
                  "type": "file",
                  "content": "This is a log file. No errors found. Another line. Yet another line. Error: Something went wrong. Final line."
                },
                "archive": {
                  "type": "directory",
                  "contents": {}
                },
                ".hidden_file": {
                  "type": "file",
                  "content": "This is a hidden file."
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.ls",
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.tail"
  ],
  "involved_classes": [
    "GorillaFileSystem"
  ],
  "missed_function": {
    "2": [
      "mv"
    ]
  },
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_miss_func_2",
  "question": "[[{\"role\": \"user\", \"content\": \"Go into `documents` folder and Could you draft up a create a document titled 'TeamNotes.txt' for keeping track of all the fresh ideas?\"}], [{\"role\": \"user\", \"content\": \"We've gathered a couple of wise insights from Simona, so could you jot down 'Collaboration leads to success. Innovation ignites growth.' into the previous file?\"}], [{\"role\": \"user\", \"content\": \"There seems to be some differences noted by Simona between the 'ideas.txt' file and our 'TeamNotes.txt'. Could you delve into these files to identify and explain the line-by-line distinctions for her?\"}], [{\"role\": \"user\", \"content\": \"Simona thinks it's a smart move to secure 'TeamNotes.txt'. How about we copy it over to the archive directory under the name IdeasArchive.txt while keeping the original i...<truncated>",
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "simona": {
          "type": "directory",
          "contents": {
            "documents": {
              "type": "directory",
              "contents": {
                "ideas.txt": {
                  "type": "file",
                  "content": "Collaboration leads to success. Innovation ignites growth."
                },
                "Archived": {
                  "type": "directory",
                  "contents": {}
                },
                "past_projects": {
                  "type": "directory",
                  "contents": {}
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.touch",
    "GorillaFileSystem.echo",
    "GorillaFileSystem.diff",
    "GorillaFileSystem.cp",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.cat",
    "TicketAPI.close_ticket"
  ],
  "involved_classes": [
    "TicketAPI",
    "GorillaFileSystem"
  ],
  "missed_function": {
    "4": [
      "cp",
      "cat"
    ]
  },
  "excluded_function": [
    "rm"
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\BFCL_v4_multi_turn_miss_param.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/5.0/8
- top-level keys: ['excluded_function', 'id', 'initial_config', 'involved_classes', 'path', 'question']
#### sample[0]
```json
{
  "id": "multi_turn_miss_param_0",
  "question": [
    [
      {
        "role": "user",
        "content": "Move 'final_report.pdf' within document directory to 'temp' directory in document. Make sure to create the directory"
      }
    ],
    [
      {
        "role": "user",
        "content": "Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension."
      }
    ],
    [
      {
        "role": "user",
        "content": "Move one of the file in document directory to temp as well and having final report also there, proceed to juxtapose it with 'previous_report.pdf' to detect any critical alterations."
      }
    ],
    [
      {
        "role": "user",
        "content": "The specific file is previous_report.pdf."
      }
    ]
  ],
  "initial_config": "{\"GorillaFileSystem\": {\"root\": {\"workspace\": {\"type\": \"directory\", \"contents\": {\"document\": {\"type\": \"directory\", \"contents\": {\"final_report.pdf\": {\"type\": \"file\", \"content\": \"Year2024 This is the final report content including budget analysis and other sections.\"}, \"previous_report.pdf\": {\"type\": \"file\", \"content\": \"Year203 This is the previous report content with different budget analysis.\"}, \"report_final.pdf\": {\"type\": \"file\", \"content\": \"Year2024 This is another final report with summary and conclusions.\"}}}, \"archive\": {\"type\": \"directory\", \"contents\": {}}}}}}, \"TwitterAPI\": {\"tweet_counter\": 3, \"tweets\": {\"0\": {\"id\": 0, \"username\": \"analyst_pro\", \"content\": \"Just finished analyzing the reports!\", \"tags\": [\"#analysis\", \"#reports\"], \"mentions\": []}, \"1\": {\"id\": 1, \"username\": \"analyst...<truncated>",
  "path": [
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.sort",
    "GorillaFileSystem.diff",
    "TwitterAPI.post_tweet"
  ],
  "involved_classes": [
    "TwitterAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_miss_param_1",
  "question": [
    [
      {
        "role": "user",
        "content": "I am alex. Check if the current directory is under my name and list all the visible and hidden contents in the current directory now, please."
      }
    ],
    [
      {
        "role": "user",
        "content": "Go to workspace directory and move one of the 'log.txt' files into a new directory 'archive'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Investigate within 'log.txt' for the occurrence of the keyword 'Error'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Finally, show the last several lines the file."
      }
    ],
    [
      {
        "role": "user",
        "content": "To be exact, it should be last 20 lines."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "alex": {
          "type": "directory",
          "contents": {
            "workspace": {
              "type": "directory",
              "contents": {
                "log.txt": {
                  "type": "file",
                  "content": "This is a log file. No errors found. Another line. Yet another line. Error: Something went wrong. Final line."
                },
                "archive": {
                  "type": "directory",
                  "contents": {}
                },
                ".hidden_file": {
                  "type": "file",
                  "content": "This is a hidden file."
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.ls",
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.tail"
  ],
  "involved_classes": [
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "cp"
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_miss_param_2",
  "question": "[[{\"role\": \"user\", \"content\": \"Go into document folder and Could you draft up a document for keeping track of all the fresh ideas?\"}], [{\"role\": \"user\", \"content\": \"The document name should be 'TeamNotes.txt'.\"}], [{\"role\": \"user\", \"content\": \"We've gathered a couple of wise insights from Simona, so could you jot down 'Collaboration leads to success. Innovation ignites growth.' into the previous file?\"}], [{\"role\": \"user\", \"content\": \"There seems to be some differences noted by Simona between the 'ideas.txt' file and our 'TeamNotes.txt'. Could you delve into these files to identify and explain the line-by-line distinctions for her?\"}], [{\"role\": \"user\", \"content\": \"Simona thinks it's a smart move to secure 'TeamNotes.txt'. How about we copy it over to the archive directory under the name I...<truncated>",
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "simona": {
          "type": "directory",
          "contents": {
            "documents": {
              "type": "directory",
              "contents": {
                "ideas.txt": {
                  "type": "file",
                  "content": "Collaboration leads to success. Innovation ignites growth."
                },
                "Archived": {
                  "type": "directory",
                  "contents": {}
                },
                "past_projects": {
                  "type": "directory",
                  "contents": {}
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.touch",
    "GorillaFileSystem.echo",
    "GorillaFileSystem.diff",
    "GorillaFileSystem.cp",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.cat",
    "TicketAPI.close_ticket"
  ],
  "involved_classes": [
    "TicketAPI",
    "GorillaFileSystem"
  ],
  "excluded_function": [
    "rm"
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_base.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 1/4.0/7
- top-level keys: ['ground_truth', 'id']
#### sample[0]
```json
{
  "id": "multi_turn_base_0",
  "ground_truth": [
    [
      "cd(folder='document')",
      "mkdir(dir_name='temp')",
      "mv(source='final_report.pdf', destination='temp')"
    ],
    [
      "cd(folder='temp')",
      "grep(file_name='final_report.pdf',pattern='budget analysis')"
    ],
    [
      "sort('final_report.pdf')"
    ],
    [
      "cd(folder='..')",
      "mv(source='previous_report.pdf',destination='temp')",
      "cd(folder='temp')",
      "diff(file_name1='final_report.pdf',file_name2='previous_report.pdf')"
    ]
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_base_1",
  "ground_truth": [
    [
      "ls(a=True)"
    ],
    [
      "cd(folder='workspace')",
      "mv(source='log.txt',destination='archive')"
    ],
    [
      "cd(folder='archive')",
      "grep(file_name='log.txt',pattern='Error')"
    ],
    [
      "tail(file_name='log.txt',lines=20)"
    ]
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_base_2",
  "ground_truth": [
    [
      "cd(folder='documents')",
      "touch(file_name='TeamNotes.txt')"
    ],
    [
      "echo(content='Collaboration leads to success. Innovation ignites growth.',file_name='TeamNotes.txt')"
    ],
    [
      "diff(file_name1='ideas.txt', file_name2='TeamNotes.txt')"
    ],
    [
      "cp(source='TeamNotes.txt',destination='Archived')",
      "cd(folder='Archived')",
      "mv(source='TeamNotes.txt',destination='IdeasArchive.txt')"
    ],
    [
      "cat(file_name='IdeasArchive.txt')"
    ]
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_long_context.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 1/4.0/7
- top-level keys: ['ground_truth', 'id']
#### sample[0]
```json
{
  "id": "multi_turn_long_context_0",
  "ground_truth": [
    [
      "cd(folder='document')",
      "mkdir(dir_name='temp')",
      "mv(source='final_report.pdf', destination='temp')"
    ],
    [
      "cd(folder='temp')",
      "grep(file_name='final_report.pdf',pattern='budget analysis')"
    ],
    [
      "sort('final_report.pdf')"
    ],
    [
      "cd(folder='..')",
      "mv(source='previous_report.pdf',destination='temp')",
      "cd(folder='temp')",
      "diff(file_name1='final_report.pdf',file_name2='previous_report.pdf')"
    ]
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_long_context_1",
  "ground_truth": [
    [
      "ls(a=True)"
    ],
    [
      "cd(folder='workspace')",
      "mv(source='log.txt',destination='archive')"
    ],
    [
      "cd(folder='archive')",
      "grep(file_name='log.txt',pattern='Error')"
    ],
    [
      "tail(file_name='log.txt',lines=20)"
    ]
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_long_context_2",
  "ground_truth": [
    [
      "cd(folder='documents')",
      "touch(file_name='TeamNotes.txt')"
    ],
    [
      "echo(content='Collaboration leads to success. Innovation ignites growth.',file_name='TeamNotes.txt')"
    ],
    [
      "diff(file_name1='ideas.txt', file_name2='TeamNotes.txt')"
    ],
    [
      "cp(source='TeamNotes.txt',destination='Archived')",
      "cd(folder='Archived')",
      "mv(source='TeamNotes.txt',destination='IdeasArchive.txt')"
    ],
    [
      "cat(file_name='IdeasArchive.txt')"
    ]
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_func.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/5.0/8
- top-level keys: ['ground_truth', 'id']
#### sample[0]
```json
{
  "id": "multi_turn_miss_func_0",
  "ground_truth": [
    [
      "cd(folder='document')",
      "mkdir(dir_name='temp')",
      "mv(source='final_report.pdf', destination='temp')"
    ],
    [
      "cd(folder='temp')",
      "grep(file_name='final_report.pdf',pattern='budget analysis')"
    ],
    [],
    [
      "sort('final_report.pdf')"
    ],
    [
      "cd(folder='..')",
      "mv(source='previous_report.pdf',destination='temp')",
      "cd(folder='temp')",
      "diff(file_name1='final_report.pdf',file_name2='previous_report.pdf')"
    ]
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_miss_func_1",
  "ground_truth": [
    [
      "ls(a=True)"
    ],
    [],
    [
      "cd(folder='workspace')",
      "mv(source='log.txt',destination='archive')"
    ],
    [
      "cd(folder='archive')",
      "grep(file_name='log.txt',pattern='Error')"
    ],
    [
      "tail(file_name='log.txt',lines=20)"
    ]
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_miss_func_2",
  "ground_truth": [
    [
      "cd(folder='documents')",
      "touch(file_name='TeamNotes.txt')"
    ],
    [
      "echo(content='Collaboration leads to success. Innovation ignites growth.',file_name='TeamNotes.txt')"
    ],
    [
      "diff(file_name1='ideas.txt', file_name2='TeamNotes.txt')"
    ],
    [],
    [
      "cp(source='TeamNotes.txt',destination='Archived')",
      "cd(folder='Archived')",
      "mv(source='TeamNotes.txt',destination='IdeasArchive.txt')"
    ],
    [
      "cat(file_name='IdeasArchive.txt')"
    ]
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\possible_answer\BFCL_v4_multi_turn_miss_param.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/5.0/8
- top-level keys: ['ground_truth', 'id']
#### sample[0]
```json
{
  "id": "multi_turn_miss_param_0",
  "ground_truth": [
    [
      "cd(folder='document')",
      "mkdir(dir_name='temp')",
      "mv(source='final_report.pdf', destination='temp')"
    ],
    [
      "cd(folder='temp')",
      "grep(file_name='final_report.pdf',pattern='budget analysis')"
    ],
    [
      "sort('final_report.pdf')"
    ],
    [],
    [
      "cd(folder='..')",
      "mv(source='previous_report.pdf',destination='temp')",
      "cd(folder='temp')",
      "diff(file_name1='final_report.pdf',file_name2='previous_report.pdf')"
    ]
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_miss_param_1",
  "ground_truth": [
    [
      "ls(a=True)"
    ],
    [
      "cd(folder='workspace')",
      "mv(source='log.txt',destination='archive')"
    ],
    [
      "cd(folder='archive')",
      "grep(file_name='log.txt',pattern='Error')"
    ],
    [],
    [
      "tail(file_name='log.txt',lines=20)"
    ]
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_miss_param_2",
  "ground_truth": [
    [],
    [
      "cd(folder='documents')",
      "touch(file_name='TeamNotes.txt')"
    ],
    [
      "echo(content='Collaboration leads to success. Innovation ignites growth.',file_name='TeamNotes.txt')"
    ],
    [
      "diff(file_name1='ideas.txt', file_name2='TeamNotes.txt')"
    ],
    [
      "cp(source='TeamNotes.txt',destination='Archived')",
      "cd(folder='Archived')",
      "mv(source='TeamNotes.txt',destination='IdeasArchive.txt')"
    ],
    [
      "cat(file_name='IdeasArchive.txt')"
    ]
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\possible_answer\BFCL_v4_multi_turn_composite.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/6.0/9
- top-level keys: ['ground_truth', 'id']
#### sample[0]
```json
{
  "id": "multi_turn_composite_0",
  "ground_truth": [
    [],
    [
      "cd(folder='document')",
      "mkdir(dir_name='temp')",
      "mv(source='final_report.pdf', destination='temp')"
    ],
    [
      "cd(folder='temp')",
      "grep(file_name='final_report.pdf',pattern='budget analysis')"
    ],
    [],
    [
      "sort('final_report.pdf')"
    ],
    [
      "cd(folder='..')",
      "mv(source='previous_report.pdf',destination='temp')",
      "cd(folder='temp')",
      "diff(file_name1='final_report.pdf',file_name2='previous_report.pdf')"
    ]
  ]
}
```
#### sample[1]
```json
{
  "id": "multi_turn_composite_1",
  "ground_truth": [
    [],
    [
      "cd(folder='workspace')",
      "ls(a=True)"
    ],
    [
      "mv(source='log.txt',destination='archive')"
    ],
    [
      "cd(folder='archive')",
      "grep(file_name='log.txt',pattern='Error')"
    ],
    [],
    [
      "tail(file_name='log.txt',lines=20)"
    ]
  ]
}
```
#### sample[2]
```json
{
  "id": "multi_turn_composite_2",
  "ground_truth": [
    [
      "cd(folder='documents')",
      "touch(file_name='TeamNotes.txt')"
    ],
    [
      "echo(content='Collaboration leads to success. Innovation ignites growth.',file_name='TeamNotes.txt')"
    ],
    [
      "diff(file_name1='ideas.txt', file_name2='TeamNotes.txt')"
    ],
    [],
    [],
    [
      "ls()",
      "cp(source='TeamNotes.txt',destination='Archived')",
      "cd(folder='Archive')",
      "mv(source='TeamNotes.txt',destination='IdeasArchive.txt')"
    ],
    [
      "cat(file_name='IdeasArchive.txt')"
    ]
  ]
}
```

### `apu_characterization\out\cap01\live_sources\bfcl-wheel\unpacked\bfcl_eval\data\unused_datasets\question\BFCL_v4_multi_turn_composite.json`
- format: JSONL (despite .json extension)
- record_count: 200
- distinct ids: 200
- turns/list-field min/med/max: 2/6.0/9
- top-level keys: ['id', 'initial_config', 'involved_classes', 'missed_function', 'path', 'question']
#### sample[0]
```json
{
  "id": "multi_turn_composite_0",
  "question": [
    [
      {
        "role": "user",
        "content": "Move a specific file within the document directory to a new directory in document. Make sure to create the directory."
      }
    ],
    [
      {
        "role": "user",
        "content": "The file name is 'final_report.pdf' and the new directory is 'temp'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Perform a detailed search to identify sections in the file pertaining to 'budget analysis'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension."
      }
    ],
    [],
    [
      {
        "role": "user",
        "content": "Move 'previous_report.pdf' in document directory to temp as well and having final report also there, proceed to juxtapose it with 'previous_report.pdf' to detect any critical alterations."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "workspace": {
          "type": "directory",
          "contents": {
            "document": {
              "type": "directory",
              "contents": {
                "final_report.pdf": {
                  "type": "file",
                  "content": "Year2024 This is the final report content including budget analysis and other sections."
                },
                "previous_report.pdf": {
                  "type": "file",
                  "content": "Year203 This is the previous report content with different budget analysis."
                }
              }
            },
            "archive": {
              "type": "directory",
              "contents": {}
            }
          }
        }
      }
    },
    "TwitterAPI": {
      "tweet_count": 3,
      "tweet_list": [
        "Just finished analyzing the reports!",
        "Budget analysis insights coming soon!",
        "Stay tuned for more updates!"
      ]
    }
  },
  "path": [
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.sort",
    "GorillaFileSystem.diff",
    "TwitterAPI.post_tweet"
  ],
  "involved_classes": [
    "TwitterAPI",
    "GorillaFileSystem"
  ],
  "missed_function": {
    "4": [
      "sort"
    ]
  }
}
```
#### sample[1]
```json
{
  "id": "multi_turn_composite_1",
  "question": [
    [
      {
        "role": "user",
        "content": "I am alex. Go into directory name after my name and list all the visible and hidden contents in the current directory now, please."
      }
    ],
    [],
    [
      {
        "role": "user",
        "content": "Move one of the 'log.txt' files into a new directory 'archive'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Investigate within 'log.txt' for the occurrence of the keyword 'Error'."
      }
    ],
    [
      {
        "role": "user",
        "content": "Finally, show the last 20 lines of a specific file for me."
      }
    ],
    [
      {
        "role": "user",
        "content": "The file name is 'log.txt'."
      }
    ]
  ],
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "alex": {
          "type": "directory",
          "contents": {
            "workspace": {
              "type": "directory",
              "contents": {
                "log.txt": {
                  "type": "file",
                  "content": "This is a log file. No errors found. Another line. Yet another line. Error: Something went wrong. Final line."
                },
                "archive": {
                  "type": "directory",
                  "contents": {}
                },
                ".hidden_file": {
                  "type": "file",
                  "content": "This is a hidden file."
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.ls",
    "GorillaFileSystem.find",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.grep",
    "GorillaFileSystem.tail"
  ],
  "involved_classes": [
    "GorillaFileSystem"
  ],
  "missed_function": {
    "1": [
      "ls"
    ]
  }
}
```
#### sample[2]
```json
{
  "id": "multi_turn_composite_2",
  "question": "[[{\"role\": \"user\", \"content\": \"Go into document folder and Could you draft up a create a document titled 'TeamNotes.txt' for keeping track of all the fresh ideas?\"}], [{\"role\": \"user\", \"content\": \"We've gathered a couple of wise insights from Simona, so could you jot down 'Collaboration leads to success. Innovation ignites growth.' into the previous file?\"}], [{\"role\": \"user\", \"content\": \"There seems to be some differences noted by Simona between the 'ideas.txt' file and our 'TeamNotes.txt'. Could you delve into these files to identify and explain the line-by-line distinctions for her?\"}], [{\"role\": \"user\", \"content\": \"Simona thinks it's a smart move to secure a certain file. How about we copy it over to the 'Archived' directory under a new name while keeping the original intact? Make sure...<truncated>",
  "initial_config": {
    "GorillaFileSystem": {
      "root": {
        "simona": {
          "type": "directory",
          "contents": {
            "documents": {
              "type": "directory",
              "contents": {
                "ideas.txt": {
                  "type": "file",
                  "content": "Collaboration leads to success. Innovation ignites growth."
                },
                "Archived": {
                  "type": "directory",
                  "contents": {}
                },
                "past_projects": {
                  "type": "directory",
                  "contents": {}
                }
              }
            }
          }
        }
      }
    }
  },
  "path": [
    "GorillaFileSystem.touch",
    "GorillaFileSystem.echo",
    "GorillaFileSystem.diff",
    "GorillaFileSystem.cp",
    "GorillaFileSystem.mv",
    "GorillaFileSystem.cat",
    "TicketAPI.close_ticket"
  ],
  "involved_classes": [
    "TicketAPI",
    "GorillaFileSystem"
  ],
  "missed_function": {
    "5": [
      "ls"
    ]
  }
}
```

## CAP-01 live agent run search

- `cap01/runs` exists=True
- `cap01/results` exists=False
- `cap01/trajectories` exists=False
- `cap01/live_runs` exists=False
- `cap01/matrix` exists=False
- `cap01/stage` exists=False
- pools_triage jsonl files: 260
- example `apu_characterization\out\cap01\pools_triage\frontier_staging\frontier-EXT-001.jsonl` records=4 keys=['candidate_id', 'completion_tokens', 'content', 'generation_request_id', 'ordinal', 'prompt_tokens', 'task_id']
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

## TLP-01 structure

- _gate_smoke/
- dependence_graphs/
- dependence_graphs_v2/
- t1_t2_boundary_stage1.md
- t2/
- traces/

### `apu_characterization\out\tlp01\dependence_graphs_v2\S2-MT-CMP-01-s0\Tier_0.json`
- keys: ['control_edge_count', 'data_edge_count', 'edge_class_counts', 'edge_count', 'edges', 'graph_format', 'is_dag', 'nodes', 'ordering_conservation', 'session_id', 'tier', 'topological_levels']
```json
{
  "control_edge_count": 3,
  "data_edge_count": 0,
  "edge_class_counts": {
    "HO": 1,
    "SC-EMIT": 2
  },
  "edge_count": 3,
  "edges": [
    {
      "derivation_ref": "parent_turn:0->tool_call:1",
      "dst_seq": 1,
      "edge_class": "SC-EMIT",
      "kind": "control",
      "reason": "SC-EMIT",
      "src_seq": 0,
      "tier": "Tier_0"
    },
    {
      "derivation_ref": "parent_turn:0->tool_call:2",
      "dst_seq": 2,
      "edge_class": "SC-EMIT",
      "kind": "control",
      "reason": "SC-EMIT",
      "src_seq": 0,
      "tier": "Tier_0"
    },
    {
      "derivation_ref": "harness_order:1->2(seq 1->2)",
      "dst_seq": 2,
      "edge_class": "HO",
      "kind": "control",
      "reason": "HO",
      "src_seq": 1,
      "tier": "Tier_0"
    }
  ],
  "graph_format": "tlp01_graph_v2",
  "is_dag": true,
  "nodes": [
    0,
    1,
    2
  ],
  "ordering_conservation": {
    "adjacent_pairs": 2,
    "explained_pairs": 2,
    "pass": true,
    "unexplained": []
  },
  "session_id": "S2-MT-CMP-01-s0",
  "tier": "Tier_0",
  "topological_levels": [
    [
      0
    ],
    [
      1
    ],
    [
      2
    ]
  ]
}
```

### `apu_characterization\out\tlp01\t2\aggregate.json`
- keys: ['aggregate_sha256', 'banded_session_count', 'blocked_claims', 'bystander_contention', 'ceiling_claim', 'claim', 'data_source', 'floor_tax_m2_minus_m1b', 'frontier_claim', 'headline_form', 'm0_g_v', 'm1a_speedup_bands', 'm1a_speedup_bands_by_source', 'm1b_speedup_bands', 'm1b_speedup_bands_by_source', 'm2_speedup_bands', 'm2_speedup_bands_by_source', 'm3_speedup_bands', 'm5_at_optimal_policy', 'ownable_firsts', 'phase_diagram', 'protocol_version', 'replication_floor', 'session_count', 'sparse_descriptive', 'speculation_headroom', 't1_index_sha256', 'validity_class']
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
    "secondary": true
  },
  "ceiling_claim": {
    "criterion": "Tier_C_TLP_lt_1.5x_broadly",
    "data_source": "real_t0_trace",
    "language": "agents near-serial at the turn level; value shifts to the frontier track",
    "multi_tool_tier_c_m1_bands": {
      "LH-01": {
        "max": 1.0,
        "median": 1.0,
        "min": 1.0
      },
      "LH-02": {
        "max": 1.0,
        "median": 1.0,
        "min": 1.0
      },
      "MT-CMP-01": {
        "max": 1.0,
        "median": 1.0,
        "min"
```

### `apu_characterization\out\tlp01\_gate_smoke\m4_predictor\phase_diagram.json`
- keys: ['accuracy_grid', 'boundary', 'cell_count', 'm3_zero_point_note', 'natural_predictor_accuracy', 'optimal_by_penalty_accuracy', 'penalties_ns', 'policies', 'praetor_label', 'praetor_penalty_key', 'praetor_region', 'pre_registered_hypothesis', 'region_map']
```json
{
  "accuracy_grid": [
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9
  ],
  "boundary": {
    "exists": true,
    "policy_invariant": false,
    "transitions": [
      {
        "accuracy_target": 0.3,
        "boundary_penalty_ns": 1000000,
        "from_penalty_key": "5ms",
        "from_policy": "breadth_3",
        "to_penalty_key": "1ms",
        "to_policy": "breadth_2"
      },
      {
        "accuracy_target": 0.4,
        "boundary_penalty_ns": 5000000,
        "from_penalty_key": "10ms_software",
        "from_policy": "breadth_2",
        "to_penalty_key": "5ms",
        "to_policy": "breadth_5"
      },
      {
        "accuracy_target": 0.5,
        "boundary_penalty_ns": 500000,
        "from_penalty_key": "1ms",
        "from_policy": "breadth_3",
        "to_penalty_key": "500us",
        "to_policy": "breadth_5"
      },
      {
        "accuracy_target": 0.6,
        "boundary_penalty_ns": 1000000,
        "from_penalty_key": "5ms",
        "from_policy": "breadth_2",
        "to_penalty_key": "1ms",
        "to_policy": "always_top1"
      },
      {
        "accuracy_target": 0.7,
        "boundary_penalty_ns": 5000000,
        "from_penalty_key": "10ms_software",
        "from_policy": "breadth_5",
        "to_penalty_key": "5ms",
        "to_policy": "always_top1"
      },
      {
        "accuracy_target": 0.8,
        "boundary_penalty_ns": 1000000,
        "from_penalty_key": "5ms",
        "from_policy": "confidence_gated",
        "to_penalty_key": "1ms",
        "to_policy": "always_top1"
      },
      {
        "accuracy_target": 0.9,
        "boundary_penalty_ns": 1000000,
        "from_penalty_key": "5ms",
        "from_policy": "breadth_3",
        "to_penalty_key": "1ms",
        "to_policy": "confidence_gated"
      }
    ]
  },
  "cell_count": 588,
  "m3_zero_point_note": "no_speculation policy is the M3 zero point",
  "natural_predictor_accuracy": {
    "n_predictions": 7.0,
    "top1_accuracy": 1.0
  },
  "optim
```

### `apu_characterization\out\tlp01\t2\partition.json`
- keys: ['behavior', 'eligible_task_ids', 'required_seeds', 'sparse_task_ids']
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
      "s
```

### `apu_characterization\out\tlp01\t2\quotable_extracts.json`
- keys: ['aggregate_sha', 'bystander', 'canonical_rung_1b', 'canonical_rung_3a', 'ceiling_rung', 'composite_sentence', 'floor_tax_m2_minus_m1b', 'frontier', 'frontier_rung', 'graph_input_sha', 'm1a_bands', 'm1b_bands', 'speculation_headroom']
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
  "canonical_rung_3a": "Under a perfect non-speculative scheduler (M1a), the conservative dependence floor (Tier-C) finds agent turn-level work broadly near-serial (~1\u00d7) across this ta
```

## MCP-01 / mcp_tax nature check

- COMPLETE.json count: 22
- example `apu_characterization\out\mcp_tax\fixphase_resmoke_v10_p512_after_readfix\runs\stdio\t-stdio__p-524288__s-flat_5__n-1__i-raw_jsonrpc__m-throttle\0\COMPLETE.json`
- keys: ['cell_id', 'cell_plan_sha256', 'complete', 'files', 'layout_version', 'protocol_version', 'seed']
```json
{
  "cell_id": "t-stdio__p-524288__s-flat_5__n-1__i-raw_jsonrpc__m-throttle",
  "cell_plan_sha256": "d29d812e29ec3754f7d1d5538a899f285898a5acd2c35ab12069e54d6c5ac1d0",
  "complete": true,
  "files": {
    "client/result.json": "95be6196d499bec327f938971887d941ab3d7fb2c849dcc2166edd4f743fbe5b",
    "manifest.json": "4c5bda0fa31a9aad8078ab8198d5e2abd4c8e490a051ede7e6f950b733a62d5d",
    "plan.json": "b38887d9e5e051a2e4cefc72ee044830deea33813642ad101e4e38cef05c2705",
    "server/result.json": "9e5b2006ff719f38d3fbead1e01d3c15e9399ba825c0b8ac94fa246d42181c49",
    "server_config.json": "5e8a3a446f3152999495835870e48c79a0f8718c09acead92b3e6a561aff4647",
    "wire/10_request_0.bin": "71a737108e66266e54ecb2bce9e7c1af9e30c6eb831d3f8b1fbd1d8ac9f46b12",
    "wire/10_response_1.bin": "df282869712fe24a8a4cfca90bde89fe602a6ce0202d8a6d1b59694caa2b2867",
    "wire/11_request_0.bin": "f1f2427c73d8191929c0290f3427c7398d5a10523d6f3952159465d5d5bec77a",
    "wire/11_response_1.bin": "bb90ec61d32103b02cf2e686c54b2abba3bfe499957c74f8250f7abaa88b8633",
    "wire/12_request_0.bin": "4b22823df001abfc4be1017326a4362effbd4e9b465515f9b1399802b113a034",
    "wire/12_response_1.bin": "006a8b6dfffd02f88ae524add78a23d8b6ec47407a6d158a1951fa8bba671901",
    "wire/13_request_0.bin": "f4e5305ae9561e451ae74998a3776095392214a18c156ceb1b6809846b7912bf",
    "wire/13_response_1.bin": "7fbaae69374bdd87b168405f6f77817769cfb418d1577c7a318e172f52fa33a7",
    "wire/14_request_0.bin": "84589dc59560280d3853d27185f23653049bf826726f3d295ac112a759fd0d2b",
    "wire/14_response_1.bin": "08c008b453a9f8c4693f765ceea86edb9d705ac0347b3554fd6a12eae2f94fd0",
    "wire/15_request_0.bin": "ab32834b021dfcdaf8bc800e7a93a5b41c2e59144f3b9301081795d80da64ff6",
    "wire/15_response_1.bin": "c2a4e50365e89902edf0a3904944eea3cba2df348bc6ce9d4259e6114fb07b21",
    "wire/16_request_0.bin": "416d67ddcf4770ab100862210fb33fd321834f4e5a15c72d19be771bc8f938b7",
    "wire/16_response_1.bin": "551f2c6db86972d0a5a1743b113313e4bc19ce3282083a7ee57b2bd59a7249e2",
    "wire/17_request_0.bin": "d3a27f4cc92afcd641456b511432a757f776a0de68cc0e3f6f6fecbcd7f634fa",
    "wire/17_response_1.bin": "2209dd8f2cfc380dda189764e03dc15a7bd7e473c358623842b5f03d3fa67cb6",
    "wire/18_request_0.bin": "b79bf79b9029af9cbbfefcf218557304a0b36a18f602076ef07d8c33c56c1fe4",
    "wire/18_response_1.bin": "d014024e6c435d844e751cf6c51d5bb06f6c1c0881a38d7fe4d72c3f612ae5ca",
    "wire/19_request_0.bin": "1cd70ec2e9363aaa09cce0c7e2f7b5770a3468c5e8f14a176cb9de90bc
```
- doc `apu_characterization\out\mcp_tax\mcp01_authenticity_audit.md` size=10988
- doc `apu_characterization\out\mcp_tax\mcp01_v10_120x5_launch.md` size=2532
- doc `apu_characterization\out\mcp_tax\mcp01_v10_prelaunch_note.md` size=2159
- doc `apu_characterization\out\mcp_tax\mcp01_v10_presmoke_gate.md` size=6555

## Other aggregates: tool-sequence presence

- `real_agent_breakdown.json` size=88677 has_toolish_fields=True top_keys=['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'task_assignments', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'category_regions_override', 'reproduce_cmd', 'per_task', 'category_averages', 'per_task_wall_cpu', 'behavior_buckets', 'amenability_tiers', 'invariant', 'audit']
  - `task_assignments` list len=10 item_keys=['task_id', 'profile', 'goal', 'turns']
- `real_agent_breakdown_remote_search.json` size=28648 has_toolish_fields=True top_keys=['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'task_assignments', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'category_regions_override', 'reproduce_cmd', 'per_task', 'category_averages', 'per_task_wall_cpu', 'behavior_buckets', 'amenability_tiers', 'invariant', 'batch_attribution', 'audit']
  - `task_assignments` list len=1 item_keys=['task_id', 'profile', 'goal', 'turns']
- `replication_remote_search_v3.json` size=811583 has_toolish_fields=True top_keys=['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'git', 'measurement_git', 'env', 'config', 'aggregate', 'per_seed_artifacts', 'audit']
  - `per_seed_artifacts` list len=5 item_keys=['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'config', 'batch_wall_s', 'run', 'per_task', 'per_task_wall_cpu', 'category_averages', 'behavior_buckets', 'timer_overhead_ns_per_pair', 'task_assignments', 'invariant', 'batch_attribution', 'audit']
- `tool_locality_ablation.json` size=42359 has_toolish_fields=True top_keys=['experiment', 'result_validity', 'generated_utc', 'setup_ref', 'git', 'env', 'config', 'timer_overhead_ns_per_pair', 'batch_wall_s', 'run', 'per_task', 'per_task_wall_cpu', 'session_rows', 'comparison', 'interpretation', 'reproduce_cmd', 'invariant']
  - `run` dict n=10 value_keys=[]

## Parquet/SQLite

- *.parquet: 16
  - `apu_characterization\out\turntrace_v2\cpu_dryrun\corpus\call_records.parquet` (16166)
  - `apu_characterization\out\turntrace_v2\cpu_dryrun\corpus\trajectory_records.parquet` (4066)
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C2\corpus\call_records.parquet` (14537)
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C2\corpus\trajectory_records.parquet` (4065)
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C1\corpus\call_records.parquet` (14544)
  - `apu_characterization\out\turntrace_v2\cloud_smoke\smoke_C1\corpus\trajectory_records.parquet` (4065)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_b\corpus\call_records.parquet` (18228)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_b\corpus\trajectory_records.parquet` (4546)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_a\corpus\call_records.parquet` (14699)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C2\phase_a\corpus\trajectory_records.parquet` (4162)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_b\corpus\call_records.parquet` (18370)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_b\corpus\trajectory_records.parquet` (4554)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_a\corpus\call_records.parquet` (14728)
  - `apu_characterization\out\turntrace_v2\cloud_full\cell_C1\phase_a\corpus\trajectory_records.parquet` (4162)
  - `apu_characterization\out\turntrace_v2\cloud_c1_mock\corpus\call_records.parquet` (14796)
- *.sqlite: 11
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\california_schools.sqlite` (11116544)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\card_games.sqlite` (261820416)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\codebase_community.sqlite` (481419264)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\debit_card_specializing.sqlite` (34635776)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\european_football_2.sqlite` (597754880)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\financial.sqlite` (71294976)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\formula_1.sqlite` (22360064)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\student_club.sqlite` (2641920)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\superhero.sqlite` (237568)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\thrombosis_prediction.sqlite` (7327744)
  - `apu_characterization\out\cap01\corpus_root\assets\text_to_sql\fixtures\toxicology.sqlite` (2678784)
- *.db: 0