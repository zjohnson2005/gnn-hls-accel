"""Phase A: recover OA-01 bash-verb alphabet from mini-swe-agent traj logs."""
from __future__ import annotations

import json
import re
import shlex
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OA01_RUNS = ROOT / "apu_characterization" / "out" / "oa01" / "runs"
OUT_MD = Path(__file__).resolve().parent / "oa01_alphabet.md"

# Target verb alphabet (plus OTHER, ANSWER).
KNOWN_VERBS = {
    "cd",
    "ls",
    "grep",
    "rg",
    "find",
    "cat",
    "head",
    "tail",
    "sed",
    "awk",
    "python",
    "python3",
    "pytest",
    "git",
    "echo",
    "mkdir",
    "rm",
    "rmdir",
    "touch",
    "diff",
    "open",
    "str_replace",
    "cp",
    "mv",
    "wc",
    "sort",
    "uniq",
    "tee",
    "xargs",
    "chmod",
    "pwd",
    "which",
    "basename",
    "dirname",
    "cut",
    "tr",
    "perl",
    "ruby",
    "node",
    "npm",
    "pip",
    "conda",
    "make",
    "cmake",
    "docker",
    "curl",
    "wget",
    "tar",
    "unzip",
    "jq",
    "true",
    "false",
    "test",
    "[",
    "apply_patch",
    "patch",
    "complete_task_and_submit_final_output",
    "nl",
}

# Canonical aliases → verb symbol shown in alphabet.
VERB_ALIAS = {
    "rg": "grep",
    "python3": "python",
    "rmdir": "rm",
    "[": "test",
    "complete_task_and_submit_final_output": "submit",
    "nl": "cat",  # line-numbered view ≈ cat
}

# Verbs that count as "in target set" for OTHER rate (user-requested core + aliases).
TARGET_CORE = {
    "cd",
    "ls",
    "grep",
    "find",
    "cat",
    "head",
    "tail",
    "sed",
    "awk",
    "python",
    "pytest",
    "git",
    "echo",
    "mkdir",
    "rm",
    "touch",
    "diff",
    "open",
    "str_replace",
    "OTHER",
    "ANSWER",
    "submit",  # terminal submit via bash helper
}


@dataclass
class BashCall:
    command: str
    verb: str
    chain_length: int
    raw_first_token: str


@dataclass
class TurnJoin:
    trajectory_id: str
    turn_index: int
    task_id: str
    is_tool_call: bool
    step_type_semantic: str
    n_bash_in_record: int
    n_calls_in_traj: int
    verbs: list[str] = field(default_factory=list)
    chain_lengths: list[int] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    join_ok: bool = True
    join_note: str = ""
    source: str = ""  # traj | api_boundary | none


def parse_api_boundary_calls(record: dict) -> list[BashCall]:
    """Extract bash calls from one api_boundary response_json (same shape as derive.py)."""
    value = record.get("response_json")
    if not isinstance(value, dict):
        return []
    calls_out: list[BashCall] = []
    choices = value.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            name = function.get("name")
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments}
            if name == "bash":
                cmd = str(arguments.get("command", arguments.get("_raw", "")))
                calls_out.append(extract_bash_call(cmd))
            elif name:
                calls_out.append(
                    BashCall(
                        command=f"<{name}>",
                        verb=normalize_verb(str(name)) if str(name) in KNOWN_VERBS else str(name),
                        chain_length=1,
                        raw_first_token=str(name),
                    )
                )
        return calls_out
    output = value.get("output") or (value.get("response") or {}).get("output") or []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"function_call", "tool_call"}:
            continue
        name = item.get("name")
        arguments = item.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {"_raw": arguments}
        if name == "bash":
            cmd = str(arguments.get("command", arguments.get("_raw", "")))
            calls_out.append(extract_bash_call(cmd))
    return calls_out


def load_api_by_call_id(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "raw" / "api_boundary.jsonl"
    by_id: dict[str, dict] = {}
    if not path.exists():
        return by_id
    for row in load_jsonl(path):
        cid = row.get("call_id")
        if cid:
            by_id[str(cid)] = row
    return by_id


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def split_shell_chain(command: str) -> list[str]:
    """Split on top-level |, &&, ||, ; (not inside quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    in_single = False
    in_double = False
    while i < len(command):
        ch = command[i]
        nxt = command[i + 1] if i + 1 < len(command) else ""
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if ch in {"|", ";"} or (ch == "&" and nxt == "&") or (ch == "|" and nxt == "|"):
                # handle || and &&
                if ch == "|" and nxt == "|":
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 2
                    continue
                if ch == "&" and nxt == "&":
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 2
                    continue
                if ch == "|":
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 1
                    continue
                if ch == ";":
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 1
                    continue
        buf.append(ch)
        i += 1
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts or [command.strip()]


def first_token(segment: str) -> str:
    s = segment.strip()
    # strip env assignments: FOO=bar cmd
    while True:
        m = re.match(r"^[A-Za-z_][A-Za-z0-9_]*=\S+\s+(.*)$", s)
        if m:
            s = m.group(1)
            continue
        break
    # strip leading sudo / env / command / time / nice
    for wrapper in ("sudo", "env", "command", "time", "nice", "nohup"):
        if s.startswith(wrapper + " ") or s == wrapper:
            s = s[len(wrapper) :].lstrip()
    if not s:
        return ""
    # path-qualified binaries → basename
    try:
        tokens = shlex.split(s, posix=True)
    except ValueError:
        tokens = s.split()
    if not tokens:
        return ""
    tok = tokens[0]
    # handle `python -m pytest` → pytest as verb? keep python; note separately later
    base = Path(tok).name
    return base.lower()


def normalize_verb(raw: str) -> str:
    if not raw:
        return "OTHER"
    if raw in VERB_ALIAS:
        return VERB_ALIAS[raw]
    if raw in KNOWN_VERBS:
        return raw
    # python -c / scripts often invoked as ./script.sh
    if raw.endswith(".py"):
        return "python"
    if raw.endswith(".sh"):
        return "OTHER"
    return "OTHER"


def extract_bash_call(command: str) -> BashCall:
    # Drop leading full-line comments before verb extraction.
    cleaned_lines = []
    for line in command.splitlines():
        if cleaned_lines or not line.strip().startswith("#"):
            cleaned_lines.append(line)
    command = "\n".join(cleaned_lines).strip() or command
    segments = split_shell_chain(command)
    first = segments[0] if segments else command
    raw = first_token(first)
    # Special-case: python -m pytest → pytest
    try:
        tokens = shlex.split(first, posix=True)
    except ValueError:
        tokens = first.split()
    verb_raw = raw
    if verb_raw in {"python", "python3"} and len(tokens) >= 3 and tokens[1] == "-m":
        mod = tokens[2].lower()
        if mod in {"pytest", "unittest", "pip"}:
            verb_raw = mod
    # mini-swe-agent submit idiom: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt
    if "complete_task_and_submit_final_output" in command.lower():
        verb_raw = "complete_task_and_submit_final_output"
    verb = normalize_verb(verb_raw)
    return BashCall(
        command=command,
        verb=verb,
        chain_length=len(segments),
        raw_first_token=raw,
    )


def parse_assistant_calls(msg: dict) -> list[BashCall]:
    calls: list[BashCall] = []
    # Prefer structured tool_calls
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"_raw": args}
        if name == "bash":
            cmd = str(args.get("command", args.get("_raw", "")))
            calls.append(extract_bash_call(cmd))
        elif name:
            # non-bash tool (rare)
            calls.append(
                BashCall(
                    command=f"<{name}>",
                    verb=normalize_verb(name) if name in KNOWN_VERBS else name,
                    chain_length=1,
                    raw_first_token=name,
                )
            )
    if calls:
        return calls
    # Fallback: extra.actions
    extra = msg.get("extra") or {}
    for action in extra.get("actions") or []:
        cmd = str(action.get("command", ""))
        if cmd:
            calls.append(extract_bash_call(cmd))
    return calls


def find_traj(run_dir: Path) -> Path | None:
    subj = run_dir / "subject"
    hits = sorted(subj.rglob("*.traj.json")) if subj.exists() else []
    if not hits:
        hits = sorted(run_dir.rglob("*.traj.json"))
    return hits[0] if hits else None


def semantic_bucket(step_type: str) -> set[str]:
    """Map step_type_semantic atoms to expected verb families for agreement."""
    mapping = {
        "inspect": {"ls", "grep", "find", "cat", "head", "tail", "sed", "awk", "wc", "pwd", "diff"},
        "inspect_diff": {"git", "diff"},
        "edit": {"sed", "apply_patch", "patch", "tee", "python", "perl", "echo", "cp", "mv", "rm", "touch", "mkdir"},
        "verify": {"pytest", "python", "make", "npm", "tox"},
        "install": {"pip", "npm", "conda", "apt"},
        "reproduce_or_probe": {"python", "node", "ruby"},
        "submit": {"submit"},
        "shell_other": set(),  # anything
        "reason_or_finalize": {"ANSWER"},
    }
    atoms = [a for a in step_type.split("+") if a]
    expected: set[str] = set()
    for a in atoms:
        expected |= mapping.get(a, set())
    return expected


def main() -> None:
    run_dirs = sorted([p for p in OA01_RUNS.iterdir() if p.is_dir() and p.name.startswith("OA01-")])
    lines: list[str] = ["# OA-01 Alphabet Recovery (Phase A)\n"]
    lines.append("## 1. `.traj.json` schema\n")
    lines.append(f"Found **{len(list(OA01_RUNS.rglob('*.traj.json')))}** `*.traj.json` files under `out/oa01/runs/`.\n")

    # Schema from first traj that has an assistant message with tool_calls
    sample_traj = None
    sample_obj = None
    asst = None
    for cand in sorted(OA01_RUNS.rglob("*.traj.json")):
        obj = json.loads(cand.read_text(encoding="utf-8"))
        msgs = obj.get("messages") or []
        hit = next(
            (
                m
                for m in msgs
                if m.get("role") == "assistant" and (m.get("tool_calls") or m.get("extra"))
            ),
            None,
        )
        if hit is not None:
            sample_traj, sample_obj, asst = cand, obj, hit
            break
    if sample_traj is None or sample_obj is None or asst is None:
        raise RuntimeError("No OA-01 .traj.json with assistant tool_calls found")
    lines.append(f"Example file: `{sample_traj.relative_to(ROOT)}`\n")
    lines.append("### Top-level schema\n")
    lines.append("```")
    lines.append(f"trajectory_format: {sample_obj.get('trajectory_format')!r}")
    lines.append(f"instance_id: {sample_obj.get('instance_id')!r}")
    lines.append(f"keys: {sorted(sample_obj.keys())}")
    info = sample_obj.get("info") or {}
    lines.append(f"info.keys: {sorted(info.keys()) if isinstance(info, dict) else type(info)}")
    msgs = sample_obj.get("messages") or []
    role_c = Counter(m.get("role") for m in msgs)
    lines.append(f"messages: list len={len(msgs)} roles={dict(role_c)}")
    lines.append(f"assistant message keys: {sorted(asst.keys())}")
    tc0 = (asst.get("tool_calls") or [None])[0]
    if tc0:
        lines.append(f"tool_calls[0] keys: {sorted(tc0.keys())}")
        lines.append(f"tool_calls[0].function keys: {sorted((tc0.get('function') or {}).keys())}")
    lines.append("```\n")

    lines.append("### Three sample assistant messages (verbatim bash commands)\n")
    # Collect diverse samples across corpus
    samples_shown = 0
    for traj_path in sorted(OA01_RUNS.rglob("*.traj.json")):
        obj = json.loads(traj_path.read_text(encoding="utf-8"))
        for msg in obj.get("messages") or []:
            if msg.get("role") != "assistant":
                continue
            calls = parse_assistant_calls(msg)
            if not calls:
                continue
            lines.append(f"#### Sample from `{traj_path.relative_to(ROOT)}`")
            content = msg.get("content") or ""
            lines.append("Content (truncated to 800 chars):")
            lines.append("```")
            lines.append(content[:800])
            lines.append("```")
            lines.append("tool_calls / commands:")
            lines.append("```json")
            payload = []
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                payload.append({"name": fn.get("name"), "arguments": args})
            lines.append(json.dumps(payload, indent=2)[:2500])
            lines.append("```\n")
            samples_shown += 1
            if samples_shown >= 3:
                break
        if samples_shown >= 3:
            break

    # ------------------------------------------------------------------
    # Join + verb extraction
    # Primary: traj.json assistant[i] ↔ turn_index i
    # Fallback: raw/api_boundary.jsonl via turn_records.call_id
    #   (same archive derive.py used; needed when traj truncated / missing)
    # ------------------------------------------------------------------
    joins: list[TurnJoin] = []
    missing_traj_runs: list[str] = []
    traj_count_mismatches: list[str] = []
    verb_counter: Counter[str] = Counter()
    other_commands: list[str] = []
    call_level_verbs: list[str] = []
    chain_len_counter: Counter[int] = Counter()
    fanout_counter: Counter[int] = Counter()
    source_counter: Counter[str] = Counter()

    agreement_ok = 0
    agreement_total = 0
    agreement_by_atom: Counter[str] = Counter()
    disagreement_examples: list[str] = []
    traj_primary_ok = 0
    traj_primary_attempted = 0

    def score_agreement(tj: TurnJoin) -> None:
        nonlocal agreement_ok, agreement_total
        if not tj.join_ok or not tj.verbs:
            return
        expected = semantic_bucket(tj.step_type_semantic)
        agreement_total += 1
        if tj.step_type_semantic == "reason_or_finalize":
            if tj.verbs == ["ANSWER"]:
                agreement_ok += 1
                agreement_by_atom["reason_or_finalize:ok"] += 1
            else:
                agreement_by_atom["reason_or_finalize:miss"] += 1
                if len(disagreement_examples) < 20:
                    disagreement_examples.append(
                        f"{tj.trajectory_id} t{tj.turn_index}: semantic=reason_or_finalize "
                        f"verbs={tj.verbs} cmds={tj.commands[:2]}"
                    )
            return
        if "shell_other" in tj.step_type_semantic.split("+") and not expected - set():
            # pure shell_other (or only shell_other atoms with empty map)
            pass
        if not expected:
            agreement_ok += 1
            agreement_by_atom["shell_other_or_unknown:ok"] += 1
            return
        # Zip atoms to calls when lengths match; else majority family match
        atoms = [a for a in tj.step_type_semantic.split("+") if a]
        if len(atoms) == len(tj.verbs):
            hits = 0
            for atom, verb in zip(atoms, tj.verbs):
                fam = semantic_bucket(atom)
                if not fam or verb in fam:
                    hits += 1
            ok = hits == len(atoms)
        else:
            hits = sum(1 for v in tj.verbs if v in expected)
            ok = hits >= max(1, (len(tj.verbs) + 1) // 2)
        if ok:
            agreement_ok += 1
            agreement_by_atom["family:ok"] += 1
        else:
            agreement_by_atom["family:miss"] += 1
            if len(disagreement_examples) < 20:
                disagreement_examples.append(
                    f"{tj.trajectory_id} t{tj.turn_index}: semantic={tj.step_type_semantic} "
                    f"verbs={tj.verbs} expected⊃{sorted(expected)[:8]} cmds={tj.commands[:2]}"
                )

    def ingest_calls(tj: TurnJoin, calls: list[BashCall]) -> None:
        tj.n_calls_in_traj = len(calls)
        if not calls:
            tj.verbs = ["ANSWER"]
            tj.commands = []
            tj.chain_lengths = [0]
            fanout_counter[0] += 1
            verb_counter["ANSWER"] += 1
            call_level_verbs.append("ANSWER")
            return
        if len(calls) != tj.n_bash_in_record and tj.n_bash_in_record > 0:
            note = f"fanout_mismatch src={len(calls)} record={tj.n_bash_in_record}"
            tj.join_note = f"{tj.join_note}; {note}" if tj.join_note else note
        for c in calls:
            tj.verbs.append(c.verb)
            tj.commands.append(c.command)
            tj.chain_lengths.append(c.chain_length)
            verb_counter[c.verb] += 1
            call_level_verbs.append(c.verb)
            chain_len_counter[c.chain_length] += 1
            if c.verb == "OTHER":
                other_commands.append(c.command)
        fanout_counter[len(calls)] += 1

    for run_dir in run_dirs:
        turn_path = run_dir / "derived" / "turn_records.jsonl"
        if not turn_path.exists():
            continue
        records = load_jsonl(turn_path)
        traj_path = find_traj(run_dir)
        api_by_id = load_api_by_call_id(run_dir)
        assistants: list[dict] = []
        if traj_path is None:
            missing_traj_runs.append(run_dir.name)
        else:
            obj = json.loads(traj_path.read_text(encoding="utf-8"))
            assistants = [m for m in (obj.get("messages") or []) if m.get("role") == "assistant"]
            if len(assistants) != len(records):
                traj_count_mismatches.append(
                    f"{run_dir.name}: assistants={len(assistants)} turn_records={len(records)}"
                )

        tid = records[0].get("trajectory_id", run_dir.name) if records else run_dir.name
        for r in records:
            idx = int(r["turn_index"])
            tj = TurnJoin(
                trajectory_id=r.get("trajectory_id", tid),
                turn_index=idx,
                task_id=r.get("task_id", ""),
                is_tool_call=bool(r.get("is_tool_call")),
                step_type_semantic=str(r.get("step_type_semantic", "")),
                n_bash_in_record=len(r.get("tool_names") or []),
                n_calls_in_traj=0,
            )
            calls: list[BashCall] | None = None

            # Primary: traj
            traj_primary_attempted += 1
            if 0 <= idx < len(assistants):
                calls = parse_assistant_calls(assistants[idx])
                # Empty calls on a tool turn is NOT a successful primary recovery
                if calls or not r.get("is_tool_call"):
                    tj.source = "traj"
                    tj.join_ok = True
                    traj_primary_ok += 1
                    if not calls and r.get("is_tool_call"):
                        tj.join_note = "traj_empty_on_tool_turn"
                else:
                    calls = None
                    tj.join_note = "traj_empty_on_tool_turn"
            else:
                if traj_path is None:
                    tj.join_note = "no_traj_json"
                elif not assistants:
                    tj.join_note = "traj_has_zero_assistant_messages"
                else:
                    tj.join_note = (
                        f"turn_index {idx} out of range for {len(assistants)} assistant msgs"
                    )

            # Fallback: api_boundary by call_id
            if calls is None:
                call_id = r.get("call_id")
                api_row = api_by_id.get(str(call_id)) if call_id else None
                if api_row is not None:
                    calls = parse_api_boundary_calls(api_row)
                    tj.source = "api_boundary"
                    tj.join_ok = True
                    if tj.join_note:
                        tj.join_note = f"{tj.join_note}; recovered_via_api_boundary"
                    else:
                        tj.join_note = "recovered_via_api_boundary"
                else:
                    tj.join_ok = False
                    tj.source = "none"
                    tj.join_note = f"{tj.join_note}; api_boundary_miss" if tj.join_note else "api_boundary_miss"
                    joins.append(tj)
                    source_counter["none"] += 1
                    continue

            ingest_calls(tj, calls)
            source_counter[tj.source] += 1
            score_agreement(tj)
            joins.append(tj)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    n_turns = len(joins)
    n_ok = sum(1 for j in joins if j.join_ok)
    n_fail = n_turns - n_ok
    fail_notes = Counter(j.join_note for j in joins if j.join_note)

    lines.append("## 2. Join to `derived/turn_records.jsonl`\n")
    lines.append(f"- OA01 run dirs: {len(run_dirs)}")
    lines.append(f"- turn_records rows: {n_turns}")
    lines.append(
        f"- **traj-primary join** (assistant[i] present and usable): "
        f"{traj_primary_ok}/{traj_primary_attempted} "
        f"({100*traj_primary_ok/max(1,traj_primary_attempted):.1f}%)"
    )
    lines.append(
        f"- **final join_ok** (traj OR api_boundary fallback): "
        f"{n_ok}/{n_turns} ({100*n_ok/max(1,n_turns):.1f}%)"
    )
    lines.append(f"- hard join failures (neither source): {n_fail}")
    lines.append("- recovery source counts:")
    for k, v in source_counter.most_common():
        lines.append(f"  - `{k}`: {v}")
    if missing_traj_runs:
        lines.append(f"- runs with no usable `.traj.json` path/content: {missing_traj_runs}")
        lines.append(
            "  - note: `OA01-M-10-matplotlib__matplotlib-25433` has `subject/` but no "
            "`.traj.json` (only `minisweagent.log`); commands recovered from `api_boundary.jsonl`."
        )
    if traj_count_mismatches:
        lines.append("- assistant/turn_record count mismatches (traj truncated vs API turns):")
        for x in traj_count_mismatches:
            lines.append(f"  - {x}")
        lines.append(
            "  - typical cause: final `submit` / `reason_or_finalize` turns present in "
            "`turn_records` + `api_boundary` but missing from the subject `.traj.json`."
        )
    lines.append("- join notes (top):")
    for k, v in fail_notes.most_common(25):
        if k:
            lines.append(f"  - `{k}`: {v}")

    fanout_mismatch = sum(1 for j in joins if "fanout_mismatch" in j.join_note)
    lines.append(f"- fanout mismatches (recovered calls ≠ record tool_names len): {fanout_mismatch}")
    lines.append("\n### Fanout distribution (calls per joined turn; 0 = ANSWER)\n")
    lines.append("| calls/turn | count |")
    lines.append("|---:|---:|")
    for k in sorted(fanout_counter):
        lines.append(f"| {k} | {fanout_counter[k]} |")

    lines.append("\n## 3. Verb alphabet\n")
    lines.append(
        "Normalization: take FIRST verb of each bash invocation; for pipes/`&&`/`||`/`;` "
        "chains record `chain_length` separately. Strip flags/args via first-token only. "
        "Aliases: `rg→grep`, `python3→python`, `python -m pytest→pytest`, "
        "`complete_task_and_submit_final_output→submit`.\n"
    )
    total_syms = sum(verb_counter.values())
    other_n = verb_counter.get("OTHER", 0)
    other_pct = 100.0 * other_n / max(1, total_syms)
    lines.append(f"- total call-level symbols (incl. ANSWER turns): **{total_syms}**")
    lines.append(f"- distinct verbs: **{len(verb_counter)}**")
    lines.append(f"- OTHER: **{other_n}** ({other_pct:.1f}%)")
    lines.append("\n### Frequency distribution\n")
    lines.append("| verb | count | pct |")
    lines.append("|---|---:|---:|")
    for verb, cnt in verb_counter.most_common():
        lines.append(f"| `{verb}` | {cnt} | {100*cnt/max(1,total_syms):.1f}% |")

    lines.append("\n### Chain length distribution\n")
    lines.append("| chain_length | count |")
    lines.append("|---:|---:|")
    for k in sorted(chain_len_counter):
        lines.append(f"| {k} | {chain_len_counter[k]} |")

    if other_pct > 15.0 or other_n > 0:
        lines.append("\n### Top unmatched OTHER commands (for normalizer extension)\n")
        # group by first token
        other_tok = Counter()
        other_ex: dict[str, str] = {}
        for cmd in other_commands:
            tok = first_token(split_shell_chain(cmd)[0]) or "<empty>"
            other_tok[tok] += 1
            other_ex.setdefault(tok, cmd)
        lines.append("| raw first token | count | example command |")
        lines.append("|---|---:|---|")
        for tok, cnt in other_tok.most_common(20):
            ex = other_ex[tok].replace("|", "\\|")
            if len(ex) > 120:
                ex = ex[:120] + "…"
            lines.append(f"| `{tok}` | {cnt} | `{ex}` |")
        if other_pct > 15.0:
            lines.append(
                f"\n**OTHER is {other_pct:.1f}% (>15%). Extend the normalizer before Phase B.**\n"
            )
        else:
            lines.append(
                f"\nOTHER is {other_pct:.1f}% (≤15%). Top unmatched listed for transparency.\n"
            )

    # First-call-per-turn distribution (for issue-width a)
    first_verbs = Counter()
    for j in joins:
        if j.verbs:
            first_verbs[j.verbs[0]] += 1
    lines.append("\n### First-call-per-turn distribution (issue-width target a)\n")
    lines.append("| verb | turns | pct |")
    lines.append("|---|---:|---:|")
    n_first = sum(first_verbs.values())
    for verb, cnt in first_verbs.most_common():
        lines.append(f"| `{verb}` | {cnt} | {100*cnt/max(1,n_first):.1f}% |")

    lines.append("\n## 4. Cross-check vs `step_type_semantic`\n")
    lines.append(
        "Agreement rule (coarse family match): when atom count equals call count, "
        "zip-match each atom's verb family; otherwise require a majority of verbs in "
        "the union family. Families: inspect→{ls,grep,cat,head,tail,sed,awk,…}, "
        "edit→{sed,patch,echo,cp,…}, verify→{pytest,…}, submit→{submit}, "
        "reason_or_finalize→ANSWER. `shell_other` soft-agrees.\n"
    )
    lines.append(
        f"- agreement: **{agreement_ok}/{agreement_total}** "
        f"({100*agreement_ok/max(1,agreement_total):.1f}%)"
    )
    lines.append("- breakdown:")
    for k, v in sorted(agreement_by_atom.items()):
        lines.append(f"  - `{k}`: {v}")
    lines.append(
        "\n**Interpretation:** low family agreement is expected and informative. "
        "`step_type_semantic` (from `derive._command_semantic`) labels *intent* "
        "(e.g. edit via `cat > file <<EOF`, or submit via "
        "`echo COMPLETE_TASK… && cat patch.txt`), while the verb alphabet labels "
        "*surface command*. These are complementary, not duplicates. "
        "Submit turns are normalized to `submit` when the command contains "
        "`COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`."
    )
    if disagreement_examples:
        lines.append("\nDisagreement examples (pre-submit-normalization style / family misses):")
        for ex in disagreement_examples[:15]:
            lines.append(f"- {ex}")

    # Persist join table for Phase B
    out_jsonl = Path(__file__).resolve().parent / "oa01_verb_turns.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as f:
        for j in joins:
            f.write(
                json.dumps(
                    {
                        "trajectory_id": j.trajectory_id,
                        "turn_index": j.turn_index,
                        "task_id": j.task_id,
                        "is_tool_call": j.is_tool_call,
                        "step_type_semantic": j.step_type_semantic,
                        "verbs": j.verbs,
                        "commands": j.commands,
                        "chain_lengths": j.chain_lengths,
                        "n_bash_in_record": j.n_bash_in_record,
                        "n_calls_in_traj": j.n_calls_in_traj,
                        "join_ok": j.join_ok,
                        "join_note": j.join_note,
                        "source": j.source,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    lines.append(f"\n---\nWrote join table: `{out_jsonl.relative_to(ROOT)}`\n")
    lines.append("**STOP — Phase A complete. Await alphabet review before Phase B.**\n")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"verbs: {verb_counter.most_common()}")
    print(f"OTHER%={other_pct:.1f} join_ok={n_ok}/{n_turns}")
    print(f"agreement={agreement_ok}/{agreement_total}")


if __name__ == "__main__":
    main()
