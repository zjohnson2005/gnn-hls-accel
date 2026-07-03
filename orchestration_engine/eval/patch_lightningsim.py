"""Patch installed LightningSim for Vitis 2023.2+ generated csim sources.

Vitis >= ~2023.2 emits generated csim support sources (e.g.
``.autopilot/db/mapper_<kernel>.cpp``) whose first line is
``#include "hls_signal_handler.h"``. That header is generated into the
solution tree (typically ``csim/build/``) and is NOT part of
``$XILINX_HLS/include``, so LightningSim's support-code compiles fail with
``hls_signal_handler.h: No such file or directory``.

This script idempotently patches the *installed* ``lightningsim/runner.py``
to pass the solution's generated-source directories (``.autopilot/db``,
``csim/build``) plus a bundled ``compat_include/`` fallback on every
generated-source / testbench compile. The real Vitis-generated header wins
when present; the stub only exists so older/odd project layouts still build
(the real header merely installs csim crash-diagnostic signal handlers).

Usage:
    python -m orchestration_engine.eval.patch_lightningsim [solution_dir]

If ``solution_dir`` is given and contains a real ``hls_signal_handler.h``,
it is copied into ``compat_include/`` so the genuine header is always found.
"""

import re
import shutil
import sys
from pathlib import Path

MARKER = "# OE-PATCH v1: add solution generated-source include dirs (Vitis 2023.2+)"

STUB_HEADER = """\
// Stub hls_signal_handler.h installed by gnn-hls-accel's LightningSim patch.
// The Vitis-generated original (solution csim/build/) only installs signal
// handlers for nicer csim crash diagnostics; omitting them is functionally
// safe for LightningSim trace capture. If the real header exists in the
// solution tree, its include dir is searched first and this stub is unused.
#ifndef OE_LS_COMPAT_HLS_SIGNAL_HANDLER_H
#define OE_LS_COMPAT_HLS_SIGNAL_HANDLER_H
#endif
"""

# (regex anchor, human name) — insert extra -I lines just before each "-c".
PATCH_POINTS = [
    (
        re.compile(r'(?P<indent>[ \t]*)"-c",\n(?P=indent)mapper_hw_input_path,'),
        "mapper (generated csim source) compile",
    ),
    (
        re.compile(
            r'(?P<indent>[ \t]*)"-c",\n(?P=indent)project_file\.path\.absolute\(\),'
        ),
        "testbench source compile",
    ),
]

EXTRA_INCLUDE_TEMPLATE = (
    '{i}"-I",\n'
    '{i}self.solution.path / ".autopilot/db",\n'
    '{i}"-I",\n'
    '{i}self.solution.path / "csim/build",\n'
    '{i}"-I",\n'
    '{i}Path(__file__).parent / "compat_include",\n'
)


def find_runner() -> Path:
    import lightningsim

    return Path(lightningsim.__file__).parent / "runner.py"


def patch_runner(runner_path: Path) -> bool:
    text = runner_path.read_text()
    if MARKER in text:
        print(f"already patched: {runner_path}")
        return True

    backup = runner_path.with_suffix(".py.oe-orig")
    if not backup.exists():
        shutil.copy2(runner_path, backup)
        print(f"backup saved: {backup}")

    applied = 0
    for pattern, name in PATCH_POINTS:

        def add_includes(match: re.Match) -> str:
            indent = match.group("indent")
            return EXTRA_INCLUDE_TEMPLATE.format(i=indent) + match.group(0)

        text, count = pattern.subn(add_includes, text, count=1)
        if count == 1:
            print(f"patched: {name}")
            applied += 1
        else:
            print(f"WARNING: anchor not found for {name} (LS version drift?)")

    if applied == 0:
        print("ERROR: no patch points matched; installed LightningSim differs "
              "from expected layout. Inspect manually:", runner_path)
        return False

    text = f"{MARKER}\n{text}"
    runner_path.write_text(text)
    print(f"patched runner written: {runner_path}")
    return True


def install_compat_header(runner_path: Path, solution_dir: Path | None) -> None:
    compat_dir = runner_path.parent / "compat_include"
    compat_dir.mkdir(exist_ok=True)
    target = compat_dir / "hls_signal_handler.h"

    real = None
    if solution_dir is not None and solution_dir.is_dir():
        real = next(solution_dir.rglob("hls_signal_handler.h"), None)

    if real is not None:
        shutil.copy2(real, target)
        print(f"real header found ({real}); copied to {target}")
    elif not target.exists():
        target.write_text(STUB_HEADER)
        print(f"stub header installed: {target}")
    else:
        print(f"compat header already present: {target}")


def main() -> int:
    solution_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    runner_path = find_runner()
    if not runner_path.is_file():
        print(f"ERROR: lightningsim runner not found at {runner_path}")
        return 1
    ok = patch_runner(runner_path)
    install_compat_header(runner_path, solution_dir)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
