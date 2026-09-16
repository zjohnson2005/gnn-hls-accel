"""Deterministic five-domain verification for CAP-01."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass
from decimal import Decimal, DecimalException, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping

from .contracts import CandidateRecord, TaskRecord, sha256_json
from .domain_verifiers import (
    DomainVerdict,
    verify_function_call,
    verify_structured_extraction,
    verify_text_to_sql,
)

VerdictStatus = Literal["pass", "wrong", "invalid", "error", "timeout"]


@dataclass(frozen=True)
class VerifierLimits:
    # HumanEval+/EvalPlus includes pathological cases (e.g. special_factorial)
    # that exceed 5s wall on CPython; 30s matches gold self-check acceptance.
    wall_seconds: float = 30.0
    cpu_seconds: int = 2
    memory_bytes: int = 256 * 1024 * 1024
    output_bytes: int = 1 * 1024 * 1024

    def validate(self) -> None:
        if self.wall_seconds <= 0 or self.cpu_seconds < 1:
            raise ValueError("verifier time limits must be positive")
        if self.memory_bytes < 16 * 1024 * 1024 or self.output_bytes < 1:
            raise ValueError("verifier memory and output limits are too small")


@dataclass(frozen=True)
class VerificationVerdict:
    task_id: str
    candidate_id: str
    domain: str
    solved: bool
    status: VerdictStatus
    digest: str
    candidate_sha256: str
    wall_ns: int
    cpu_ns: int
    stdout_sha256: str
    stderr_sha256: str
    verifier_config_sha256: str
    runtime: str
    network_isolated: bool

    def deterministic_payload(self) -> dict[str, Any]:
        """Return fields that must match during a G4 re-execution."""
        return {
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "domain": self.domain,
            "solved": self.solved,
            "status": self.status,
            "candidate_sha256": self.candidate_sha256,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "verifier_config_sha256": self.verifier_config_sha256,
            "runtime": self.runtime,
            "network_isolated": self.network_isolated,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReexecutionResult:
    stable: bool
    original_digest: str
    repeated_digest: str
    repeated: VerificationVerdict


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _extract_answer(content: str) -> str:
    marker = r"\boxed"
    marker_index = content.rfind(marker)
    if marker_index >= 0:
        opening = content.find("{", marker_index + len(marker))
        if opening >= 0:
            depth = 0
            for index in range(opening, len(content)):
                if content[index] == "{":
                    depth += 1
                elif content[index] == "}":
                    depth -= 1
                    if depth == 0:
                        return content[opening + 1 : index].strip()
    final = re.findall(
        r"(?:final\s+answer|answer)\s*[:=]\s*(.+)",
        content,
        flags=re.IGNORECASE,
    )
    if final:
        return final[-1].strip()
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    return text


def normalize_exact(value: str) -> str:
    """Normalize Unicode, math wrappers, and insignificant whitespace."""
    text = unicodedata.normalize("NFKC", _extract_answer(value))
    text = text.replace("\N{MINUS SIGN}", "-").strip()
    while len(text) >= 2 and (
        (text[0], text[-1]) in {("$", "$"), ("(", ")"), ("[", "]")}
    ):
        text = text[1:-1].strip()
    return " ".join(text.split())


def normalize_numeric(value: str) -> Decimal:
    """Parse a finite decimal, fraction, LaTeX fraction, or percentage."""
    text = normalize_exact(value).replace(",", "").strip()
    latex = re.fullmatch(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", text)
    if latex:
        text = f"{latex.group(1)}/{latex.group(2)}"
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    try:
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            number = Decimal(numerator) / Decimal(denominator)
        else:
            number = Decimal(text)
    except (DecimalException, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"not a numeric answer: {value!r}") from exc
    if percent:
        number /= Decimal(100)
    if not number.is_finite():
        raise ValueError("numeric answer must be finite")
    return number


def _math_expected(config: Mapping[str, Any]) -> str:
    for key in ("answer", "expected", "reference_answer"):
        if key in config:
            return str(config[key])
    raise ValueError("MATH verifier requires answer or expected")


def verify_math(
    task: TaskRecord,
    candidate: CandidateRecord,
) -> VerificationVerdict:
    config = dict(task.verifier)
    mode = str(config.get("mode", config.get("type", "exact"))).lower()
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    status: VerdictStatus = "wrong"
    solved = False
    try:
        expected = _math_expected(config)
        if mode in ("numeric", "number"):
            actual_number = normalize_numeric(candidate.content)
            expected_number = normalize_numeric(expected)
            absolute = Decimal(str(config.get("abs_tol", config.get("tolerance", 0))))
            relative = Decimal(str(config.get("rel_tol", 0)))
            if (
                not absolute.is_finite()
                or not relative.is_finite()
                or absolute < 0
                or relative < 0
            ):
                raise ValueError("numeric tolerances must be finite and non-negative")
            delta = abs(actual_number - expected_number)
            solved = delta <= max(absolute, relative * abs(expected_number))
        elif mode in ("exact", "string", "math"):
            solved = normalize_exact(candidate.content) == normalize_exact(expected)
        else:
            raise ValueError(f"unsupported MATH verifier mode: {mode}")
        status = "pass" if solved else "wrong"
    except (InvalidOperation, TypeError, ValueError):
        status = "invalid"
    wall_ns = time.perf_counter_ns() - start_wall
    cpu_ns = time.process_time_ns() - start_cpu
    config_hash = sha256_json(config)
    payload = {
        "task_id": task.task_id,
        "candidate_id": candidate.candidate_id,
        "domain": task.domain,
        "solved": solved,
        "status": status,
        "candidate_sha256": candidate.digest(),
        "stdout_sha256": _sha256(b""),
        "stderr_sha256": _sha256(b""),
        "verifier_config_sha256": config_hash,
        "runtime": "builtin-math-v1",
        "network_isolated": True,
    }
    return VerificationVerdict(
        **payload,
        digest=sha256_json(payload),
        wall_ns=wall_ns,
        cpu_ns=cpu_ns,
    )


_RUNNER = r"""
import json
import socket
import sys

def blocked(*args, **kwargs):
    raise PermissionError("network disabled")

socket.socket = blocked
socket.create_connection = blocked
payload = json.loads(sys.stdin.read())
source = payload["source"]
tests = payload["tests"]
entry_point = payload.get("entry_point")
module = type(sys)("solution")
module.__file__ = "solution.py"
sys.modules["solution"] = module
exec(compile(source, "solution.py", "exec"), module.__dict__)
scope = {"solution": module, "__name__": "__cap01_hidden__"}
exec(compile(tests, "hidden_tests.py", "exec"), scope)
# HumanEval+/EvalPlus tests define check(candidate); invoke it explicitly.
check_fn = scope.get("check")
if callable(check_fn):
    if not entry_point or not isinstance(entry_point, str):
        raise ValueError("entry_point required when hidden tests define check()")
    if not hasattr(module, entry_point):
        raise AttributeError(f"solution missing entry_point {entry_point!r}")
    check_fn(getattr(module, entry_point))
"""


def _candidate_source(content: str) -> str:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:python|py)?\s*\n(.*)\n```", text, re.DOTALL)
    return fenced.group(1) if fenced else text


def _hidden_tests(config: Mapping[str, Any]) -> str:
    tests_path = config.get("tests_path")
    if isinstance(tests_path, str) and tests_path:
        path = Path(tests_path)
        if not path.is_file():
            raise ValueError("CODE verifier hidden tests file is missing")
        content = path.read_bytes()
        expected_hash = config.get("tests_sha256")
        if not isinstance(expected_hash, str) or _sha256(content) != expected_hash:
            raise ValueError("CODE verifier hidden tests hash mismatch")
        return content.decode("utf-8")
    tests = config.get("hidden_tests", config.get("tests"))
    if isinstance(tests, str) and tests.strip():
        return tests
    if isinstance(tests, list):
        lines: list[str] = []
        for index, case in enumerate(tests):
            if not isinstance(case, Mapping) or "call" not in case or "expected" not in case:
                raise ValueError("invalid structured hidden test")
            call = str(case["call"])
            if not re.fullmatch(r"[A-Za-z_]\w*", call):
                raise ValueError("structured hidden test has invalid callable name")
            args = repr(case.get("args", []))
            kwargs = repr(case.get("kwargs", {}))
            expected = repr(case["expected"])
            lines.append(
                f"assert solution.{call}(*{args}, **{kwargs}) == {expected}, "
                f"'case {index} failed'"
            )
        return "\n".join(lines)
    raise ValueError("CODE verifier requires hidden_tests")


def _child_cpu_ns() -> int:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return int((usage.ru_utime + usage.ru_stime) * 1_000_000_000)
    except (ImportError, OSError):
        times = os.times()
        return int((times.children_user + times.children_system) * 1_000_000_000)


def _limit_child(limits: VerifierLimits) -> Any:
    if os.name != "posix":
        return None

    def apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
        resource.setrlimit(
            resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes)
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (limits.output_bytes, limits.output_bytes)
        )
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        if hasattr(resource, "RLIMIT_NPROC"):
            resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))

    return apply


@lru_cache(maxsize=1)
def _network_namespace_prefix() -> tuple[list[str], bool]:
    if platform.system() != "Linux":
        return [], False
    unshare = shutil.which("unshare")
    if not unshare:
        return [], False
    try:
        probe = subprocess.run(
            [unshare, "--user", "--map-root-user", "--net", "true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], False
    if probe.returncode != 0:
        return [], False
    return [unshare, "--user", "--map-root-user", "--net"], True


def _sanitized_hash(value: bytes, temporary_path: Path) -> str:
    normalized = value.replace(os.fsencode(temporary_path), b"<sandbox>")
    return _sha256(normalized)


def verify_code(
    task: TaskRecord,
    candidate: CandidateRecord,
    *,
    limits: VerifierLimits | None = None,
) -> VerificationVerdict:
    chosen_limits = limits or VerifierLimits()
    chosen_limits.validate()
    config = dict(task.verifier)
    config_hash = sha256_json(config)
    runtime = f"CPython-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if platform.python_implementation() != "CPython":
        raise RuntimeError("CAP-01 CODE verification requires CPython")
    try:
        tests = _hidden_tests(config)
    except ValueError:
        return _code_error_verdict(task, candidate, config_hash, runtime)

    payload = json.dumps(
        {
            "source": _candidate_source(candidate.content),
            "tests": tests,
            "entry_point": config.get("entry_point"),
        },
        sort_keys=True,
    ).encode("utf-8")
    prefix, os_network_isolated = _network_namespace_prefix()
    # Do not pass -S: HumanEval+ hidden tests require numpy from site-packages.
    # Network remains blocked inside the runner; this is a deliberate CAP-01
    # sandbox tradeoff (died-ledger #11).
    command = [*prefix, sys.executable, "-B", "-c", _RUNNER]
    environment = {
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": os.environ.get("PATH", ""),
    }
    for name in ("SYSTEMROOT", "TEMP", "TMP"):
        if name in os.environ:
            environment[name] = os.environ[name]
    with tempfile.TemporaryDirectory(prefix="cap01-verifier-") as directory:
        root = Path(directory)
        stdout_path = root / "stdout.bin"
        stderr_path = root / "stderr.bin"
        start_cpu = _child_cpu_ns()
        start_wall = time.perf_counter_ns()
        try:
            with stdout_path.open("wb") as stdout_handle, stderr_path.open(
                "wb"
            ) as stderr_handle:
                completed = subprocess.run(
                    command,
                    input=payload,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    cwd=root,
                    env=environment,
                    timeout=chosen_limits.wall_seconds,
                    check=False,
                    preexec_fn=_limit_child(chosen_limits),
                )
            status: VerdictStatus = "pass" if completed.returncode == 0 else "wrong"
        except subprocess.TimeoutExpired:
            status = "timeout"
        except OSError:
            status = "error"
        try:
            stdout = stdout_path.read_bytes()[: chosen_limits.output_bytes]
        except OSError:
            stdout = b""
        try:
            stderr = stderr_path.read_bytes()[: chosen_limits.output_bytes]
        except OSError:
            stderr = b""
        wall_ns = time.perf_counter_ns() - start_wall
        cpu_ns = max(0, _child_cpu_ns() - start_cpu)
        deterministic = {
            "task_id": task.task_id,
            "candidate_id": candidate.candidate_id,
            "domain": task.domain,
            "solved": status == "pass",
            "status": status,
            "candidate_sha256": candidate.digest(),
            "stdout_sha256": _sanitized_hash(stdout, root),
            "stderr_sha256": _sanitized_hash(stderr, root),
            "verifier_config_sha256": config_hash,
            "runtime": runtime,
            "network_isolated": os_network_isolated,
        }
        return VerificationVerdict(
            **deterministic,
            digest=sha256_json(deterministic),
            wall_ns=wall_ns,
            cpu_ns=cpu_ns,
        )


def _code_error_verdict(
    task: TaskRecord,
    candidate: CandidateRecord,
    config_hash: str,
    runtime: str,
) -> VerificationVerdict:
    payload = {
        "task_id": task.task_id,
        "candidate_id": candidate.candidate_id,
        "domain": task.domain,
        "solved": False,
        "status": "invalid",
        "candidate_sha256": candidate.digest(),
        "stdout_sha256": _sha256(b""),
        "stderr_sha256": _sha256(b""),
        "verifier_config_sha256": config_hash,
        "runtime": runtime,
        "network_isolated": False,
    }
    return VerificationVerdict(
        **payload,
        digest=sha256_json(payload),
        wall_ns=0,
        cpu_ns=0,
    )


def _verify_domain_builtin(
    task: TaskRecord,
    candidate: CandidateRecord,
    verifier: Any,
) -> VerificationVerdict:
    config = dict(task.verifier)
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    result: DomainVerdict = verifier(candidate.content, config)
    wall_ns = time.perf_counter_ns() - start_wall
    cpu_ns = time.process_time_ns() - start_cpu
    output = canonical = json.dumps(
        result.output,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    error = result.error.encode("utf-8")
    status: VerdictStatus = result.status  # type: ignore[assignment]
    payload = {
        "task_id": task.task_id,
        "candidate_id": candidate.candidate_id,
        "domain": task.domain,
        "solved": result.solved,
        "status": status,
        "candidate_sha256": candidate.digest(),
        "stdout_sha256": _sha256(output),
        "stderr_sha256": _sha256(error),
        "verifier_config_sha256": sha256_json(config),
        "runtime": result.runtime,
        "network_isolated": False,
    }
    return VerificationVerdict(
        **payload,
        digest=sha256_json(payload),
        wall_ns=wall_ns,
        cpu_ns=cpu_ns,
    )


def verify_candidate(
    task: TaskRecord,
    candidate: CandidateRecord,
    *,
    limits: VerifierLimits | None = None,
) -> VerificationVerdict:
    """Verify one candidate without exposing hidden test content or output."""
    if candidate.task_id != task.task_id:
        raise ValueError("candidate and task IDs do not match")
    if task.domain == "MATH":
        return verify_math(task, candidate)
    if task.domain == "CODE":
        return verify_code(task, candidate, limits=limits)
    if task.domain == "FUNCTION_CALLING":
        return _verify_domain_builtin(task, candidate, verify_function_call)
    if task.domain == "TEXT_TO_SQL":
        return _verify_domain_builtin(task, candidate, verify_text_to_sql)
    if task.domain == "STRUCTURED_EXTRACTION":
        return _verify_domain_builtin(task, candidate, verify_structured_extraction)
    raise ValueError(f"unsupported task domain: {task.domain}")


def reexecute_verification(
    task: TaskRecord,
    candidate: CandidateRecord,
    original: VerificationVerdict,
    *,
    limits: VerifierLimits | None = None,
) -> ReexecutionResult:
    """Run the G4 postprocess re-execution and compare deterministic digests."""
    repeated = verify_candidate(task, candidate, limits=limits)
    return ReexecutionResult(
        stable=original.digest == repeated.digest,
        original_digest=original.digest,
        repeated_digest=repeated.digest,
        repeated=repeated,
    )
