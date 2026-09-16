"""Frozen D1, D2, and D5 verifier adapters for CAP-01 v2."""

from __future__ import annotations

import importlib
import importlib.util
import importlib.metadata
import json
import math
import re
import sqlite3
import time
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import canonical_json_bytes, sha256_bytes


@dataclass(frozen=True)
class DomainVerdict:
    solved: bool
    status: str
    runtime: str
    output: Any
    error: str = ""


def _asset_bytes(config: Mapping[str, Any], path_field: str, hash_field: str) -> bytes:
    path_value = config.get(path_field)
    expected = config.get(hash_field)
    if not isinstance(path_value, str) or not isinstance(expected, str):
        raise ValueError(f"{path_field} and {hash_field} are required")
    path = Path(path_value)
    if not path.is_file():
        raise ValueError(f"verifier asset is missing: {path}")
    payload = path.read_bytes()
    if sha256_bytes(payload) != expected:
        raise ValueError(f"verifier asset hash mismatch: {path}")
    return payload


def _json_candidate(content: str) -> Any:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", text, re.DOTALL | re.I)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def _load_checker(config: Mapping[str, Any]) -> tuple[Callable[..., Any], str]:
    source = _asset_bytes(config, "checker_source_path", "checker_source_sha256")
    path = Path(str(config["checker_source_path"]))
    configured_module = config.get("checker_module")
    if isinstance(configured_module, str) and configured_module:
        module = importlib.import_module(configured_module)
        module_path = Path(str(getattr(module, "__file__", ""))).resolve()
        if module_path != path.resolve():
            raise ValueError("imported BFCL checker path differs from pinned source")
    else:
        module_name = f"_cap01_bfcl_{sha256_bytes(source)[:16]}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError("unable to load pinned BFCL checker")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    target: Any = module
    callable_name = str(config.get("checker_callable") or "")
    if not callable_name:
        raise ValueError("checker_callable is required")
    for part in callable_name.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise ValueError("checker_callable does not resolve to a callable")
    return target, f"BFCL-{config.get('bfcl_version')}@{sha256_bytes(source)[:12]}"


def verify_function_call(content: str, config: Mapping[str, Any]) -> DomainVerdict:
    """Invoke a pinned BFCL checker without modifying its implementation."""
    try:
        candidate = _json_candidate(content)
        checker, runtime = _load_checker(config)
        # Licensed corpus stores gold under "reference"; synthetic fixtures used
        # "reference_call". Accept both so the pinned BFCL wrapper receives gold.
        reference = config.get(
            "reference_call", config.get("reference", config.get("expected"))
        )
        mode = str(config.get("checker_argument_mode", "candidate_reference"))
        if mode == "candidate_reference":
            result = checker(candidate, reference)
        elif mode == "bfcl_record":
            result = checker(
                {
                    "candidate": candidate,
                    "reference": reference,
                    "functions": config.get("functions"),
                    "test_category": config.get("test_category", ""),
                }
            )
        else:
            raise ValueError("unsupported checker_argument_mode")
        if isinstance(result, Mapping):
            solved = bool(
                result.get("valid", result.get("success", result.get("pass", False)))
            )
        else:
            solved = bool(result)
        return DomainVerdict(
            solved=solved,
            status="pass" if solved else "wrong",
            runtime=runtime,
            output=result,
        )
    except (AttributeError, ImportError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return DomainVerdict(
            solved=False,
            status="invalid",
            runtime="BFCL-pinned-wrapper-v1",
            output=None,
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # The adopted checker is an external pinned dependency.
        return DomainVerdict(
            solved=False,
            status="error",
            runtime="BFCL-pinned-wrapper-v1",
            output=None,
            error=f"{type(exc).__name__}: {exc}",
        )


_READ_ONLY_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}
for _name in ("SQLITE_RECURSIVE",):
    if hasattr(sqlite3, _name):
        _READ_ONLY_ACTIONS.add(getattr(sqlite3, _name))


def _read_only_authorizer(
    action: int,
    _arg1: str | None,
    _arg2: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    return sqlite3.SQLITE_OK if action in _READ_ONLY_ACTIONS else sqlite3.SQLITE_DENY


def _sql_text(content: str) -> str:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*\n(.*)\n```", text, re.DOTALL | re.I)
    if fenced:
        text = fenced.group(1).strip()
    if not text:
        raise ValueError("empty SQL candidate")
    return text


def _sql_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite SQL result")
        return value
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return str(value)


def _execute_query(
    connection: sqlite3.Connection,
    query: str,
    *,
    order_sensitive: bool,
    max_result_rows: int,
) -> tuple[tuple[str, ...], list[tuple[Any, ...]]]:
    cursor = connection.execute(query)
    if cursor.description is None:
        raise ValueError("SQL candidate did not return a result set")
    raw_columns = [str(item[0]) for item in cursor.description]
    normalized_names = [unicodedata.normalize("NFKC", item).casefold() for item in raw_columns]
    if len(normalized_names) != len(set(normalized_names)):
        raise ValueError("duplicate result column names are not canonicalizable")
    order = sorted(range(len(raw_columns)), key=lambda index: normalized_names[index])
    columns = tuple(normalized_names[index] for index in order)
    fetched = cursor.fetchmany(max_result_rows + 1)
    if len(fetched) > max_result_rows:
        raise ValueError("SQL result exceeds frozen row limit")
    rows = [
        tuple(_sql_scalar(row[index]) for index in order)
        for row in fetched
    ]
    if not order_sensitive:
        rows.sort(key=lambda row: canonical_json_bytes(row))
    return columns, rows


def _numeric_equal(first: Any, second: Any, abs_tol: float, rel_tol: float) -> bool:
    if isinstance(first, bool) or isinstance(second, bool):
        return first == second
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return math.isclose(
            float(first), float(second), abs_tol=abs_tol, rel_tol=rel_tol
        )
    return first == second


def _result_equal(
    actual: tuple[tuple[str, ...], list[tuple[Any, ...]]],
    expected: tuple[tuple[str, ...], list[tuple[Any, ...]]],
    *,
    abs_tol: float,
    rel_tol: float,
) -> bool:
    # BIRD-style execution match: compare arity + cell values only.
    # Column aliases from equivalent aggregates (COUNT(*) vs COUNT(DISTINCT x))
    # must not flip the verdict when the result bag is identical.
    if len(actual[0]) != len(expected[0]) or len(actual[1]) != len(expected[1]):
        return False
    return all(
        len(left) == len(right)
        and all(
            _numeric_equal(first, second, abs_tol, rel_tol)
            for first, second in zip(left, right)
        )
        for left, right in zip(actual[1], expected[1])
    )


def verify_text_to_sql(content: str, config: Mapping[str, Any]) -> DomainVerdict:
    """Execute one candidate and one frozen reference query on a read-only fixture."""
    runtime = f"sqlite-{sqlite3.sqlite_version}"
    try:
        _asset_bytes(config, "fixture_path", "fixture_sha256")
        candidate_query = _sql_text(content)
        reference_query = str(config["reference_query"])
        order_sensitive = bool(config.get("order_sensitive", False))
        abs_tol = float(config.get("float_abs_tolerance", 1e-6))
        rel_tol = float(config.get("float_rel_tolerance", 1e-6))
        query_timeout_ms = int(config.get("query_timeout_ms", 1000))
        max_result_rows = int(config.get("max_result_rows", 10000))
        if min(abs_tol, rel_tol) < 0:
            raise ValueError("SQL tolerances must be non-negative")
        if query_timeout_ms < 1 or max_result_rows < 1:
            raise ValueError("SQL resource limits must be positive")
        uri = (
            Path(str(config["fixture_path"])).resolve().as_uri()
            + "?mode=ro&immutable=1"
        )
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.set_authorizer(_read_only_authorizer)
            deadline = time.monotonic() + query_timeout_ms / 1000.0
            connection.set_progress_handler(
                lambda: int(time.monotonic() >= deadline),
                1000,
            )
            expected = _execute_query(
                connection,
                reference_query,
                order_sensitive=order_sensitive,
                max_result_rows=max_result_rows,
            )
            deadline = time.monotonic() + query_timeout_ms / 1000.0
            actual = _execute_query(
                connection,
                candidate_query,
                order_sensitive=order_sensitive,
                max_result_rows=max_result_rows,
            )
        solved = _result_equal(
            actual, expected, abs_tol=abs_tol, rel_tol=rel_tol
        )
        return DomainVerdict(
            solved=solved,
            status="pass" if solved else "wrong",
            runtime=runtime,
            output={"columns": actual[0], "rows": actual[1]},
        )
    except (KeyError, OSError, sqlite3.Error, TypeError, ValueError) as exc:
        return DomainVerdict(
            solved=False,
            status="invalid",
            runtime=runtime,
            output=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def _schema_at_path(schema: Mapping[str, Any], path: Sequence[str]) -> Mapping[str, Any]:
    current: Mapping[str, Any] = schema
    for part in path:
        if part.isdigit():
            item_schema = current.get("items")
            current = item_schema if isinstance(item_schema, Mapping) else {}
        else:
            properties = current.get("properties")
            item_schema = (
                properties.get(part) if isinstance(properties, Mapping) else None
            )
            current = item_schema if isinstance(item_schema, Mapping) else {}
    return current


def _pointer(path: Sequence[str]) -> str:
    if not path:
        return ""
    escaped = [part.replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(escaped)


def _normalize_date(value: str, date_order: str) -> str:
    formats = ["%Y-%m-%d", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"]
    formats.append("%m/%d/%Y" if date_order == "MDY" else "%d/%m/%Y")
    for pattern in formats:
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"invalid frozen date format: {value!r}")


def _normalize_decimal(
    value: Any,
    *,
    currency: bool,
    percent: bool,
) -> str:
    text = str(value).strip().replace(",", "")
    if currency:
        text = re.sub(r"^(?:[$€£¥]|USD|EUR|GBP|JPY)\s*", "", text, flags=re.I)
    had_percent = text.endswith("%")
    if had_percent:
        text = text[:-1].strip()
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric field: {value!r}") from exc
    if not number.is_finite():
        raise ValueError("numeric field must be finite")
    if percent and had_percent:
        number /= Decimal(100)
    return str(number.normalize())


def _normalize_extraction(
    value: Any,
    schema: Mapping[str, Any],
    config: Mapping[str, Any],
    path: tuple[str, ...] = (),
) -> Any:
    pointer = _pointer(path)
    case_sensitive = set(config.get("case_sensitive_paths") or [])
    currency_paths = set(config.get("currency_paths") or [])
    percent_paths = set(config.get("percent_paths") or [])
    unordered_paths = set(config.get("order_insensitive_paths") or [])
    node_schema = _schema_at_path(schema, path)
    schema_type = node_schema.get("type")
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {
            key: _normalize_extraction(item, schema, config, (*path, str(key)))
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        normalized = [
            _normalize_extraction(item, schema, config, (*path, str(index)))
            for index, item in enumerate(value)
        ]
        if pointer in unordered_paths:
            normalized.sort(key=canonical_json_bytes)
        return normalized
    if node_schema.get("format") == "date":
        return _normalize_date(str(value).strip(), str(config["date_order"]))
    numeric_type = schema_type in {"number", "integer"} or pointer in (
        currency_paths | percent_paths
    )
    if numeric_type and not isinstance(value, bool):
        return {
            "$decimal": _normalize_decimal(
                value,
                currency=pointer in currency_paths,
                percent=pointer in percent_paths,
            )
        }
    if isinstance(value, str):
        text = " ".join(unicodedata.normalize("NFKC", value).strip().split())
        return text if pointer in case_sensitive else text.casefold()
    return value


def verify_structured_extraction(
    content: str, config: Mapping[str, Any]
) -> DomainVerdict:
    """Validate JSON Schema conformance, then apply frozen field normalization."""
    runtime = "jsonschema-unknown/cap01_d5_norm_v1"
    try:
        import jsonschema

        runtime = (
            f"jsonschema-{importlib.metadata.version('jsonschema')}"
            "/cap01_d5_norm_v1"
        )
        schema = json.loads(
            _asset_bytes(config, "schema_path", "schema_sha256").decode("utf-8")
        )
        if not isinstance(schema, Mapping):
            raise ValueError("D5 schema root must be an object")
        candidate = _json_candidate(content)
        if not isinstance(candidate, Mapping):
            raise ValueError("D5 candidate must be a JSON object")
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(candidate)
        expected = config.get("ground_truth")
        if not isinstance(expected, Mapping):
            raise ValueError("D5 ground_truth must be an object")
        actual_normalized = _normalize_extraction(candidate, schema, config)
        expected_normalized = _normalize_extraction(expected, schema, config)
        solved = actual_normalized == expected_normalized
        return DomainVerdict(
            solved=solved,
            status="pass" if solved else "wrong",
            runtime=runtime,
            output=actual_normalized,
        )
    except (
        ImportError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        return DomainVerdict(
            solved=False,
            status="invalid",
            runtime=runtime,
            output=None,
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        # jsonschema.ValidationError is dependency-defined and intentionally
        # reported as a deterministic wrong/invalid candidate outcome.
        status = "wrong" if type(exc).__name__ == "ValidationError" else "error"
        return DomainVerdict(
            solved=False,
            status=status,
            runtime=runtime,
            output=None,
            error=f"{type(exc).__name__}: {exc}",
        )
