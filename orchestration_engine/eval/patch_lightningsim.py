"""Patch installed LightningSim for Vitis 2023.2+ and multi-file HLS projects.

Patches applied to the installed ``lightningsim/runner.py`` (backup:
``runner.py.oe-orig``):

v1 — generated csim headers (``hls_signal_handler.h``)
  Add ``-I`` paths for ``.autopilot/db``, ``csim/build``, and a bundled stub.

v2 — exclude kernel .cpp from testbench link
  LightningSim's ``project_files`` lists both the kernel and TB sources. Compiling
  the kernel .cpp with objcopy ``--redefine-sym`` to ``apatb_<kernel>_ir`` creates
  a second, uninstrumented definition of the instrumented kernel from bitcode,
  which segfaults at runtime (exit -11, empty stdout). Only compile sources
  living under the solution directory (``tb=`` files in ``hls.app``).

Usage:
    python -m orchestration_engine.eval.patch_lightningsim [solution_dir]
"""

import re
import shutil
import sys
from pathlib import Path

MARKER_V1 = "# OE-PATCH v1: add solution generated-source include dirs (Vitis 2023.2+)"
MARKER_V2 = "# OE-PATCH v2: compile only TB sources under solution/ (skip kernel .cpp)"

STUB_HEADER = """\
// Stub hls_signal_handler.h installed by gnn-hls-accel's LightningSim patch.
#ifndef OE_LS_COMPAT_HLS_SIGNAL_HANDLER_H
#define OE_LS_COMPAT_HLS_SIGNAL_HANDLER_H
#endif
"""

PATCH_V1_POINTS = [
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

PATCH_V1_INCLUDES = (
    '{i}"-I",\n'
    '{i}self.solution.path / ".autopilot/db",\n'
    '{i}"-I",\n'
    '{i}self.solution.path / "csim/build",\n'
    '{i}"-I",\n'
    '{i}Path(__file__).parent / "compat_include",\n'
)

PATCH_V2_OLD = """\
                project_source_files = [
                    file for file in project_files if file.type == ProjectFile.Type.SOURCE
                ]"""

PATCH_V2_NEW = """\
                # OE-PATCH v2: compile only TB sources under solution/ (skip kernel .cpp)
                project_source_files = [
                    file
                    for file in project_files
                    if file.type == ProjectFile.Type.SOURCE
                    and self.solution.path in file.path.parents
                ]"""


def find_runner() -> Path:
    import lightningsim

    return Path(lightningsim.__file__).parent / "runner.py"


def _ensure_backup(runner_path: Path) -> None:
    backup = runner_path.with_suffix(".py.oe-orig")
    if not backup.exists():
        shutil.copy2(runner_path, backup)
        print(f"backup saved: {backup}")


def apply_v1(text: str) -> tuple[str, bool]:
    if MARKER_V1 in text:
        return text, True

    applied = 0
    for pattern, name in PATCH_V1_POINTS:

        def add_includes(match: re.Match) -> str:
            indent = match.group("indent")
            return PATCH_V1_INCLUDES.format(i=indent) + match.group(0)

        text, count = pattern.subn(add_includes, text, count=1)
        if count == 1:
            print(f"patched v1: {name}")
            applied += 1
        else:
            print(f"WARNING: v1 anchor not found for {name}")

    if applied == 0:
        return text, False

    return f"{MARKER_V1}\n{text}", True


def apply_v2(text: str) -> tuple[str, bool]:
    if MARKER_V2 in text:
        return text, True

    if PATCH_V2_OLD not in text:
        # Already manually edited or LS version drift.
        alt = PATCH_V2_OLD.replace("                ", "        ")
        if alt in text:
            text = text.replace(alt, PATCH_V2_NEW.replace("                ", "        "))
            print("patched v2: TB-only project_source_files filter (alt indent)")
            return f"{MARKER_V2}\n{text}", True
        print("WARNING: v2 anchor not found; inspect runner.py project_source_files")
        return text, False

    text = text.replace(PATCH_V2_OLD, PATCH_V2_NEW, 1)
    print("patched v2: TB-only project_source_files filter")
    return f"{MARKER_V2}\n{text}", True


def patch_runner(runner_path: Path) -> bool:
    text = runner_path.read_text()
    _ensure_backup(runner_path)

    text, ok_v1 = apply_v1(text)
    text, ok_v2 = apply_v2(text)

    if not ok_v1 and MARKER_V1 not in text:
        print("ERROR: v1 patch failed")
        return False
    if not ok_v2 and MARKER_V2 not in text:
        print("ERROR: v2 patch failed")
        return False

    runner_path.write_text(text)
    print(f"runner ready: {runner_path}")
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
