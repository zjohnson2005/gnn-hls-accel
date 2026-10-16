"""tools/kv_compiled_readback.py: port parsing, no OpenVINO needed."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import kv_compiled_readback as kv  # noqa: E402


class _Port:
    def __init__(self, names: list[str], etype: str) -> None:
        self._names = names
        self._etype = etype

    def get_names(self) -> set[str]:
        return set(self._names)

    def get_element_type(self) -> Any:
        return self._etype


def test_cache_ports_keeps_only_cache_inputs() -> None:
    ports = [
        _Port(["input_ids"], "i64"),
        _Port(["key_cache.0"], "u4"),
        _Port(["value_cache.0"], "u4"),
        _Port(["key_cache.1"], "u4"),
        _Port(["value_cache.1"], "u8"),
        _Port(["block_indices"], "i32"),
    ]
    rows = kv.cache_ports(ports)
    assert [r["name"] for r in rows] == [
        "key_cache.0",
        "value_cache.0",
        "key_cache.1",
        "value_cache.1",
    ]
    summary = kv.summarize_ports(rows)
    assert summary["key_cache"] == {"element_types": ["u4"], "ports": 2}
    assert summary["value_cache"] == {"element_types": ["u4", "u8"], "ports": 2}
    assert summary["n_cache_ports"] == 4


def test_default_arm_passes_no_properties() -> None:
    class _Type:
        u8 = "U8"

    class _Ov:
        Type = _Type

    assert kv._kv_props(_Ov, "default") == {}
    assert kv._kv_props(_Ov, "u8") == {"KV_CACHE_PRECISION": "U8"}


def test_no_openvino_import_at_module_level() -> None:
    tree = ast.parse((ROOT / "tools" / "kv_compiled_readback.py").read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, ast.Import | ast.ImportFrom)]
    names = {a.name for n in top for a in n.names} | {
        n.module for n in top if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not any(str(x).startswith("openvino") for x in names)
