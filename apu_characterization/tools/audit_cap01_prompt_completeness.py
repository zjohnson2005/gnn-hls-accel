"""Stage A: render exact generation prompts for SQL/EXT solvability audit."""

from __future__ import annotations

import json
from pathlib import Path

from apu_characterization.cap01.contracts import TaskRecord
from apu_characterization.cap01.generation import GenerationConfig, build_generation_prompt

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "out/cap01/corpus.json"
GEN = ROOT / "out/cap01/generation_config.json"
OUT = ROOT / "out/cap01/prompt_completeness_audit.json"
REPORT = ROOT / "out/cap01/PROMPT_COMPLETENESS_AUDIT.md"

SQL_SAMPLE = [f"SQL-{i:03d}" for i in (1, 2, 10, 25, 40)]
EXT_SAMPLE = [f"EXT-{i:03d}" for i in (1, 2, 10, 25, 40)]


def _load_config() -> GenerationConfig:
    payload = json.loads(GEN.read_text(encoding="utf-8"))
    return GenerationConfig(
        model=str(payload["model"]),
        temperature=float(payload["temperature"]),
        max_completion_tokens=int(payload["max_completion_tokens"]),
        target_candidates=int(payload["target_candidates"]),
        prompt_template=str(payload.get("prompt_template", "")),
        prompt_templates=payload.get("prompt_templates") or {},
    )


def _sql_has_schema(text: str) -> bool:
    lowered = text.lower()
    return "create table" in lowered or (
        "columns:" in lowered and "table" in lowered
    )


def _ext_has_schema(text: str) -> bool:
    lowered = text.lower()
    # Schema JSON or explicit field list beyond the OCR document dump.
    if '"$schema"' in text or '"properties"' in text:
        return True
    if "target schema" in lowered and "{" in text:
        return True
    return False


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: TaskRecord.from_dict(t) for t in corpus["tasks"]}
    config = _load_config()
    rows = []
    for task_id in SQL_SAMPLE + EXT_SAMPLE:
        task = by_id[task_id]
        rendered = build_generation_prompt(task, config)
        if task.domain == "TEXT_TO_SQL":
            complete = _sql_has_schema(rendered)
            missing = None if complete else "database schema (CREATE TABLE / columns)"
            corpus_has = bool(task.verifier.get("schema_ddl") or task.verifier.get("schema"))
            root = (
                "corpus_field_gap"
                if not complete and not corpus_has and "Database:" in task.prompt
                else ("template_gap" if corpus_has and not complete else "ok")
            )
        else:
            complete = _ext_has_schema(rendered)
            missing = None if complete else "target JSON schema (field names/nesting)"
            corpus_has = bool(task.verifier.get("schema_path"))
            # Schema asset exists but not in prompt → corpus prompt wiring gap
            # (template only wraps {prompt}; schema never put into task.prompt).
            root = (
                "corpus_prompt_wiring_gap"
                if not complete and corpus_has
                else ("ok" if complete else "corpus_field_gap")
            )
        rows.append(
            {
                "task_id": task_id,
                "domain": task.domain,
                "rendered_prompt": rendered,
                "prompt_complete": complete,
                "missing_element": missing,
                "root_cause": root,
                "corpus_prompt_preview": task.prompt[:240],
                "verifier_has_schema_asset": bool(
                    task.verifier.get("schema_path")
                    or task.verifier.get("fixture_path")
                ),
            }
        )

    sql_rows = [r for r in rows if r["domain"] == "TEXT_TO_SQL"]
    ext_rows = [r for r in rows if r["domain"] == "STRUCTURED_EXTRACTION"]
    report = {
        "sql_verdict": (
            "PROMPT COMPLETE"
            if all(r["prompt_complete"] for r in sql_rows)
            else "PROMPT INCOMPLETE"
        ),
        "ext_verdict": (
            "PROMPT COMPLETE"
            if all(r["prompt_complete"] for r in ext_rows)
            else "PROMPT INCOMPLETE"
        ),
        "sql_missing": "database schema (CREATE TABLE / columns)"
        if any(not r["prompt_complete"] for r in sql_rows)
        else None,
        "ext_missing": "target JSON schema field names/nesting"
        if any(not r["prompt_complete"] for r in ext_rows)
        else None,
        "sql_root_cause": sql_rows[0]["root_cause"] if sql_rows else None,
        "ext_root_cause": ext_rows[0]["root_cause"] if ext_rows else None,
        "samples": rows,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md: list[str] = []
    md.append("# CAP-01 Prompt Completeness Audit (SQL / EXT)")
    md.append("")
    md.append(f"**SQL verdict:** `{report['sql_verdict']}` — missing: `{report['sql_missing']}`; root cause: `{report['sql_root_cause']}`")
    md.append(f"**EXT verdict:** `{report['ext_verdict']}` — missing: `{report['ext_missing']}`; root cause: `{report['ext_root_cause']}`")
    md.append("")
    md.append("## Diagnosis")
    md.append("")
    md.append(
        "- **SQL:** Corpus builder puts `Database: <db_id>` but never extracts "
        "CREATE TABLE DDL from the pinned SQLite fixture into `task.prompt`. "
        "Template only wraps `{prompt}`. Schema is available on disk via "
        "`fixture_path` but invisible to the model → structural impossibility."
    )
    md.append(
        "- **EXT:** Schema JSON is written to `schema_path` for the verifier, "
        "and the prompt says \"matching the schema\" without including the "
        "schema body. Template does not interpolate verifier assets. Exact-match "
        "against unknown field nesting is structurally under-specified."
    )
    md.append("")
    for row in rows:
        md.append(f"## {row['task_id']} (`{row['domain']}`)")
        md.append("")
        md.append(f"- complete: `{row['prompt_complete']}`")
        md.append(f"- missing: `{row['missing_element']}`")
        md.append(f"- root_cause: `{row['root_cause']}`")
        md.append("")
        md.append("```text")
        md.append(row["rendered_prompt"])
        md.append("```")
        md.append("")
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "samples"}, indent=2))
    print("wrote", OUT)
    print("wrote", REPORT)


if __name__ == "__main__":
    main()
