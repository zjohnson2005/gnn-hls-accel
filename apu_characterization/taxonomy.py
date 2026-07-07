"""Functional category taxonomy for accelerable CPU-time breakdown."""

from __future__ import annotations

from enum import Enum


class Category(str, Enum):
    ORCH_SETUP = "ORCH_SETUP"
    ORCH_DISPATCH = "ORCH_DISPATCH"
    SERIALIZATION = "SERIALIZATION"
    TOKENIZATION = "TOKENIZATION"
    PROMPT_ASSEMBLY = "PROMPT_ASSEMBLY"
    CONTEXT_MGMT = "CONTEXT_MGMT"
    HTTP_CLIENT = "HTTP_CLIENT"
    TOOL_COMPUTE = "TOOL_COMPUTE"
    LOGGING = "LOGGING"
    GC = "GC"
    RESIDUAL = "RESIDUAL"


ALL_CATEGORIES: tuple[Category, ...] = tuple(Category)
INSTRUMENTED: tuple[Category, ...] = tuple(c for c in Category if c != Category.RESIDUAL)
