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

v3 — drop -flto from testbench link (conda+LTO segfaults on some kernels)

v4 — link with conda g++/libstdc++ (``liblightningsimrt.a`` ABI)

v5 — preserve conda ``LD_LIBRARY_PATH`` when LS clears it before testbench run

Usage:
    python -m orchestration_engine.eval.patch_lightningsim [solution_dir]
"""

import re
import shutil
import sys
from pathlib import Path

MARKER_V1 = "# OE-PATCH v1: add solution generated-source include dirs (Vitis 2023.2+)"
MARKER_V2 = "# OE-PATCH v2: compile only TB sources under solution/ (skip kernel .cpp)"
MARKER_V3 = "# OE-PATCH v3: drop -flto from testbench link (conda+LTO segfaults on some kernels)"
MARKER_V4 = "# OE-PATCH v4: conda g++/libstdc++ for liblightningsimrt link ABI"
MARKER_V5 = "# OE-PATCH v5: keep conda libstdc++ on LD_LIBRARY_PATH for testbench run"

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

PATCH_V2_COMP_OLD = (
    "file for file in project_files if file.type == ProjectFile.Type.SOURCE"
)
PATCH_V2_COMP_NEW = (
    "file for file in project_files "
    "if file.type == ProjectFile.Type.SOURCE "
    "and self.solution.path in file.path.parents"
)

# Match single- or multi-line list comps (LS versions differ).
PATCH_V4_CXX_BLOCK = """\
# OE-PATCH v4: conda libstdc++ for liblightningsimrt link
_oe_conda_prefix = environ.get("CONDA_PREFIX")
if _oe_conda_prefix:
    _oe_gxx = Path(_oe_conda_prefix) / "bin/x86_64-conda-linux-gnu-g++"
    _oe_gcc = Path(_oe_conda_prefix) / "bin/x86_64-conda-linux-gnu-cc"
    if _oe_gxx.is_file():
        CXX = str(_oe_gxx)
    if _oe_gcc.is_file():
        CC = str(_oe_gcc)
"""

PATCH_V4_LD_AFTER = """\
                        "-llightningsimrt",
                        *(
                            (
                                "-L",
                                str(Path(environ["CONDA_PREFIX"]) / "lib"),
                                "-Wl,-rpath",
                                str(Path(environ["CONDA_PREFIX"]) / "lib"),
                            )
                            if environ.get("CONDA_PREFIX")
                            else ()
                        ),
"""
PATCH_V2_BLOCK_RE = re.compile(
    r"(?P<indent>^[ \t]*)project_source_files\s*=\s*\[\s*\n?"
    r"(?P<body>(?:^[ \t]+[^\n]+\n?)+?)"
    r"(?P=indent)\]",
    re.MULTILINE,
)


PATCH_V5_LD_POP_OLD = 'os.environ.pop("LD_LIBRARY_PATH", None)'
PATCH_V5_LD_POP_NEW = """\
_oe_saved_ld = os.environ.pop("LD_LIBRARY_PATH", None)
_oe_conda_lib = os.environ.get("OE_CONDA_LIB")
if not _oe_conda_lib:
    _oe_cp = os.environ.get("CONDA_PREFIX")
    if _oe_cp:
        _oe_conda_lib = str(Path(_oe_cp) / "lib")
if _oe_conda_lib:
    os.environ["LD_LIBRARY_PATH"] = _oe_conda_lib + (
        f":{_oe_saved_ld}" if _oe_saved_ld else ""
    )"""
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


def _v2_replacement(indent: str) -> str:
    inner = indent + "    "
    return (
        f"{indent}project_source_files = [\n"
        f"{inner}file\n"
        f"{inner}for file in project_files\n"
        f"{inner}if file.type == ProjectFile.Type.SOURCE\n"
        f"{inner}and self.solution.path in file.path.parents\n"
        f"{indent}]"
    )


def apply_v2(text: str) -> tuple[str, bool]:
    if MARKER_V2 in text:
        return text, True
    if "self.solution.path in file.path.parents" in text:
        print("v2 filter already present (unmarked)")
        return text, True

    if PATCH_V2_COMP_OLD in text:
        text = text.replace(PATCH_V2_COMP_OLD, PATCH_V2_COMP_NEW, 1)
        print("patched v2: TB-only project_source_files filter (inline)")
        return f"{MARKER_V2}\n{text}", True

    line_re = re.compile(
        r"file\s+for\s+file\s+in\s+project_files\s+"
        r"if\s+file\.type\s*==\s*ProjectFile\.Type\.SOURCE"
    )
    if line_re.search(text):
        text, n = line_re.subn(PATCH_V2_COMP_NEW, text, count=1)
        if n == 1:
            print("patched v2: TB-only project_source_files filter (regex line)")
            return f"{MARKER_V2}\n{text}", True

    match = PATCH_V2_BLOCK_RE.search(text)
    if match and "ProjectFile.Type.SOURCE" in match.group("body"):
        if "self.solution.path in file.path.parents" in match.group("body"):
            return text, True
        indent = match.group("indent")
        text = (
            text[: match.start()]
            + _v2_replacement(indent)
            + text[match.end() :]
        )
        print("patched v2: TB-only project_source_files filter (block rewrite)")
        return f"{MARKER_V2}\n{text}", True

    print("WARNING: v2 target not found in runner.py")
    for i, line in enumerate(text.splitlines(), 1):
        if "project_source_files" in line:
            print(f"  line {i}: {line.rstrip()}")
    return text, False


def apply_v3(text: str) -> tuple[str, bool]:
    if MARKER_V3 in text:
        return text, True
    old = '"-flto",'
    if old not in text:
        print("WARNING: v3 -flto flag not found (already removed or LS drift)")
        return text, True
    text = text.replace(old, '"-fno-lto",  # OE: was -flto', 1)
    print("patched v3: replaced -flto with -fno-lto on testbench link")
    return f"{MARKER_V3}\n{text}", True


def apply_v4(text: str) -> tuple[str, bool]:
    if MARKER_V4 in text:
        return text, True

    changed = False

    if "_oe_conda_prefix = environ.get(\"CONDA_PREFIX\")" not in text:
        cxx_re = re.compile(
            r"^(?P<indent>[ \t]*)CXX\s*=\s*environ\.get\(\"CXX\",\s*\"g\+\+\")",
            re.MULTILINE,
        )
        match = cxx_re.search(text)
        if match:
            indent = match.group("indent")
            block = "\n".join(indent + line for line in PATCH_V4_CXX_BLOCK.splitlines())
            insert_at = match.end()
            text = text[:insert_at] + "\n" + block + text[insert_at:]
            print("patched v4: prefer conda CC/CXX for testbench link")
            changed = True
        else:
            print("WARNING: v4 CXX anchor not found in runner.py")

    ld_needle = '"-llightningsimrt",'
    ld_already = '*(\n                            (\n                                "-L",\n                                str(Path(environ["CONDA_PREFIX"]) / "lib"),'
    if ld_already in text:
        print("v4 conda lib path already present (unmarked)")
        changed = True
    elif ld_needle in text and PATCH_V4_LD_AFTER.strip() not in text:
        text = text.replace(ld_needle, PATCH_V4_LD_AFTER.rstrip(), 1)
        print("patched v4: add conda -L/-rpath for libstdc++")
        changed = True
    elif ld_needle not in text:
        print("WARNING: v4 -llightningsimrt anchor not found in runner.py")

    if not changed:
        return text, False

    return f"{MARKER_V4}\n{text}", True


def apply_v5(text: str) -> tuple[str, bool]:
    if MARKER_V5 in text:
        return text, True
    if "_oe_conda_lib = os.environ.get(\"OE_CONDA_LIB\")" in text:
        print("v5 conda LD_LIBRARY_PATH preserve already present (unmarked)")
        return text, True

    if PATCH_V5_LD_POP_OLD not in text:
        alt = 'environ.pop("LD_LIBRARY_PATH", None)'
        if alt in text:
            text = text.replace(alt, PATCH_V5_LD_POP_NEW.replace("os.environ", "environ"), 1)
            print("patched v5: preserve conda LD_LIBRARY_PATH (environ alias)")
            return f"{MARKER_V5}\n{text}", True
        print("WARNING: v5 LD_LIBRARY_PATH pop anchor not found in runner.py")
        return text, True

    text = text.replace(PATCH_V5_LD_POP_OLD, PATCH_V5_LD_POP_NEW, 1)
    print("patched v5: preserve conda LD_LIBRARY_PATH for testbench run")
    return f"{MARKER_V5}\n{text}", True


def patch_runner(runner_path: Path) -> bool:
    text = runner_path.read_text()
    _ensure_backup(runner_path)

    text, ok_v1 = apply_v1(text)
    text, ok_v2 = apply_v2(text)
    text, ok_v3 = apply_v3(text)
    text, ok_v4 = apply_v4(text)
    text, ok_v5 = apply_v5(text)

    if not ok_v1 and MARKER_V1 not in text:
        print("ERROR: v1 patch failed")
        return False
    if not ok_v2 and MARKER_V2 not in text:
        print("ERROR: v2 patch failed")
        return False
    if not ok_v3 and MARKER_V3 not in text:
        print("ERROR: v3 patch failed")
        return False
    if not ok_v4 and MARKER_V4 not in text:
        print("ERROR: v4 patch failed")
        return False
    if not ok_v5 and MARKER_V5 not in text:
        print("ERROR: v5 patch failed")
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
