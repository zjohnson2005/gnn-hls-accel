"""CAP-01 shim: BFCL java_parser import without tree_sitter.

CAP-01 FUNCTION_CALLING corpus is Python-only (test_category=live_multiple).
Upstream BFCL imports this module at package load; Language(ptr, name) breaks on
tree_sitter>=0.22 and tree_sitter==0.21.3 has no cp314 wheels. Stub keeps the
import graph intact; Java AST parse is out of CAP-01 scope (died-ledger #11).
"""

from __future__ import annotations


def parse_java_function_call(source_code: str):
    raise RuntimeError(
        "CAP-01: Java function-call parsing is not enabled "
        "(corpus is Python live_multiple only)"
    )
