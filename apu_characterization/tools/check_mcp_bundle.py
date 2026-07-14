"""Data-independent completeness preflight for the MCP-01 bundle."""

from __future__ import annotations

import argparse
import importlib.metadata
import inspect
import re
import sys
from pathlib import Path

from apu_characterization.experiments.mcp_tax_matrix import load_callback
from apu_characterization.mcp_tax.contracts import enumerate_matrix, load_protocol
from apu_characterization.mcp_tax.implementations.reference_sdk import (
    PINNED_MCP_VERSION,
)
from apu_characterization.mcp_tax.isolation import (
    CorePartitions,
    CpuThread,
    CpuTopology,
    HostEnvironment,
    publication_preflight,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "apu_characterization" / "requirements-mcp.txt"
REQUIRED_DEPENDENCIES = {
    "mcp",
    "jsonschema",
    "httpx",
    "httpx-sse",
    "cryptography",
}
REQUIRED_FILES = (
    "Makefile",
    "apu_characterization/bootstrap_mcp.sh",
    "apu_characterization/build_bundle.sh",
    "apu_characterization/provision_baremetal.sh",
    "apu_characterization/run_mcp_gate.sh",
    "apu_characterization/run_mcp_bare_metal.sh",
    "apu_characterization/postprocess_mcp.sh",
    "apu_characterization/requirements-mcp.txt",
    "apu_characterization/validity.py",
    "apu_characterization/experiments/mcp_tax_matrix.py",
    "apu_characterization/mcp_tax/README.md",
    "apu_characterization/mcp_tax/execute.py",
    "apu_characterization/mcp_tax/isolation.py",
    "apu_characterization/mcp_tax/postprocess.py",
    "apu_characterization/mcp_tax/protocol_v1.json",
    "apu_characterization/tools/validate_mcp_tax.py",
)
CALLBACK = "apu_characterization.mcp_tax.execute:execute_cell"
EXACT_PIN = re.compile(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)")


def check_bundle(*, check_installed: bool = True) -> list[str]:
    errors: list[str] = []
    errors.extend(_check_required_files())
    pins, pin_errors = _read_exact_pins()
    errors.extend(pin_errors)
    if not pin_errors:
        errors.extend(_check_pin_consistency(pins, check_installed=check_installed))
    errors.extend(_check_matrix_contract())
    errors.extend(_check_callback())
    errors.extend(_check_wsl_refusal())
    return errors


def _check_required_files() -> list[str]:
    return [
        f"missing required bundle file: {relative}"
        for relative in REQUIRED_FILES
        if not (REPO_ROOT / relative).is_file()
    ]


def _read_exact_pins() -> tuple[dict[str, str], list[str]]:
    pins: dict[str, str] = {}
    errors: list[str] = []
    if not LOCK_PATH.is_file():
        return pins, [f"missing dependency lock: {LOCK_PATH}"]
    for number, raw_line in enumerate(
        LOCK_PATH.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = EXACT_PIN.fullmatch(line)
        if match is None:
            errors.append(
                f"{LOCK_PATH.name}:{number} is not an exact name==version pin"
            )
            continue
        name, version = match.groups()
        normalized = name.lower().replace("_", "-")
        if normalized in pins:
            errors.append(f"duplicate dependency pin: {normalized}")
        pins[normalized] = version
    if set(pins) != REQUIRED_DEPENDENCIES:
        errors.append(
            "dependency lock names differ: "
            f"observed={sorted(pins)} expected={sorted(REQUIRED_DEPENDENCIES)}"
        )
    return pins, errors


def _check_pin_consistency(
    pins: dict[str, str],
    *,
    check_installed: bool,
) -> list[str]:
    errors: list[str] = []
    if pins.get("mcp") != PINNED_MCP_VERSION:
        errors.append(
            "official SDK code pin does not match requirements-mcp.txt: "
            f"{PINNED_MCP_VERSION!r} != {pins.get('mcp')!r}"
        )
    if check_installed:
        for package, expected in sorted(pins.items()):
            try:
                observed = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                errors.append(f"pinned dependency is not installed: {package}=={expected}")
                continue
            if observed != expected:
                errors.append(
                    f"installed dependency mismatch: {package}=={observed}, "
                    f"required {package}=={expected}"
                )
    return errors


def _check_matrix_contract() -> list[str]:
    errors: list[str] = []
    mandatory = enumerate_matrix()
    extended = enumerate_matrix(include_http_stream=True)
    if len(mandatory) != 120:
        errors.append(f"mandatory matrix has {len(mandatory)} cells, expected 120")
    if len(extended) != 160:
        errors.append(f"extended matrix has {len(extended)} cells, expected 160")
    seeds = [int(seed) for seed in load_protocol()["primary"]["seeds"]]
    if seeds != [0, 1, 2, 3, 4]:
        errors.append(f"protocol seeds are {seeds}, expected exactly [0, 1, 2, 3, 4]")
    return errors


def _check_callback() -> list[str]:
    try:
        callback = load_callback(CALLBACK)
        signature = inspect.signature(callback)
    except Exception as exc:
        return [f"execution callback cannot be loaded: {CALLBACK}: {exc}"]
    if len(signature.parameters) != 2:
        return [
            f"execution callback must accept (plan, run_dir), observed {signature}"
        ]
    return []


def _check_wsl_refusal() -> list[str]:
    threads = {
        cpu: CpuThread(
            cpu=cpu,
            package_id=0,
            core_id=cpu // 2,
            siblings=frozenset({cpu - cpu % 2, cpu - cpu % 2 + 1}),
            governor="performance",
        )
        for cpu in range(6)
    }
    topology = CpuTopology(frozenset(range(6)), threads)
    partitions = CorePartitions(
        os_cpus=frozenset({0, 1}),
        client_cpus=frozenset({2, 3}),
        server_cpus=frozenset({4, 5}),
    )
    wsl = HostEnvironment(
        system="Linux",
        release="microsoft-standard-WSL2",
        is_wsl=True,
        is_virtualized=True,
        virtualization="wsl",
    )
    publication = publication_preflight(
        topology,
        partitions,
        mode="publication",
        environment=wsl,
    )
    smoke = publication_preflight(
        topology,
        partitions,
        mode="smoke",
        environment=wsl,
    )
    errors: list[str] = []
    if publication.passed or not any("WSL" in error for error in publication.errors):
        errors.append("publication preflight does not refuse synthetic WSL")
    if not smoke.passed or not any("WSL" in caveat for caveat in smoke.caveats):
        errors.append("smoke preflight does not preserve the synthetic WSL caveat")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="check lock syntax/coherence without requiring installed distributions",
    )
    args = parser.parse_args()
    errors = check_bundle(check_installed=not args.source_only)
    print("MCP-01 bundle preflight")
    print(f"dependency_mode={'source-only' if args.source_only else 'installed-exact'}")
    if errors:
        print("FAIL:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("matrix=120 mandatory / 160 extended")
    print("seeds=0,1,2,3,4")
    print(f"callback={CALLBACK}")
    print("publication_wsl_refusal=PASS")
    print("OK")


if __name__ == "__main__":
    main()
