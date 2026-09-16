"""CAP-01 shim: BFCL js_parser import without tree_sitter.

See java_parser.py — Python-only CAP-01 FC corpus; import-graph stub only.
"""

from __future__ import annotations


def parse_javascript_function_call(source_code: str):
    raise RuntimeError(
        "CAP-01: JavaScript function-call parsing is not enabled "
        "(corpus is Python live_multiple only)"
    )
