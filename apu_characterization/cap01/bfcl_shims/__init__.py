"""Install CAP-01 BFCL import shims before loading bfcl_eval.ast_checker."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass


@dataclass(frozen=True)
class _Cap01ModelConfig:
    """Minimal stand-in for BFCL ModelConfig fields used by ast_checker."""

    underscore_to_dot: bool = False


def install_bfcl_parser_shims() -> None:
    """Replace java/js parsers that require tree_sitter 0.21.x Language(ptr, name).

    Must run before ``bfcl_eval.model_handler.utils`` (or any importer of the
    real parsers) is first imported.
    """
    from apu_characterization.cap01.bfcl_shims import java_parser, js_parser

    sys.modules["bfcl_eval.model_handler.parser.java_parser"] = java_parser
    sys.modules["bfcl_eval.model_handler.parser.js_parser"] = js_parser


def install_bfcl_model_config_shim() -> None:
    """Stub MODEL_CONFIG_MAPPING so ast_checker does not import API handlers.

    Upstream ``ast_checker`` only needs ``underscore_to_dot`` for the model name
    we pass (``cap01``). Importing real ``model_config`` pulls Claude/OpenAI
    handler stacks and their optional deps.
    """
    name = "bfcl_eval.constants.model_config"
    if name in sys.modules and hasattr(sys.modules[name], "MODEL_CONFIG_MAPPING"):
        mapping = sys.modules[name].MODEL_CONFIG_MAPPING
        if "cap01" not in mapping:
            mapping["cap01"] = _Cap01ModelConfig()
        return
    module = types.ModuleType(name)
    module.MODEL_CONFIG_MAPPING = {"cap01": _Cap01ModelConfig()}  # type: ignore[attr-defined]
    sys.modules[name] = module


def install_bfcl_runtime_shims() -> None:
    install_bfcl_parser_shims()
    install_bfcl_model_config_shim()
