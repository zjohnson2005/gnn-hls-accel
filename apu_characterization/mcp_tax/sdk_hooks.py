"""Version-locked registration for explicit SDK instrumentation hooks.

Opaque SDK internals are never monkey-patched. An SDK integration must expose
``register_mcp_tax_hook(name, context_factory)`` (or the generic equivalent
``register_hook``); otherwise coverage is recorded as unavailable and the
unmeasured CPU remains residual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, ContextManager, Iterable, Mapping

from .accum import McpMessageAccumulator
from .instrument import mcp_timed
from .taxonomy import McpCategory


@dataclass(frozen=True)
class SdkHookSpec:
    name: str
    category: McpCategory


DEFAULT_HOOK_SPECS: tuple[SdkHookSpec, ...] = (
    SdkHookSpec("message_serialize", McpCategory.MSG_SERIAL),
    SdkHookSpec("message_validate", McpCategory.MSG_VALIDATE),
    SdkHookSpec("message_frame", McpCategory.MSG_FRAME),
    SdkHookSpec("transport_cpu", McpCategory.MSG_TRANSPORT_CPU),
    SdkHookSpec("message_dispatch", McpCategory.MSG_DISPATCH),
)


@dataclass
class SdkHookRegistration:
    sdk_name: str
    expected_version: str
    observed_version: str | None
    requested_hooks: int
    registered_hooks: list[str] = field(default_factory=list)
    unavailable_hooks: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    registration_api: str | None = None
    _unregister: list[Callable[[], Any]] = field(
        default_factory=list, repr=False
    )

    @property
    def version_match(self) -> bool:
        return self.observed_version == self.expected_version

    @property
    def coverage_fraction(self) -> float:
        return (
            len(self.registered_hooks) / self.requested_hooks
            if self.requested_hooks
            else 1.0
        )

    @property
    def complete(self) -> bool:
        return self.version_match and len(self.registered_hooks) == self.requested_hooks

    def as_dict(self) -> dict[str, Any]:
        return {
            "sdk_name": self.sdk_name,
            "expected_version": self.expected_version,
            "observed_version": self.observed_version,
            "version_match": self.version_match,
            "requested_hooks": self.requested_hooks,
            "registered_hooks": len(self.registered_hooks),
            "registered_hook_names": sorted(self.registered_hooks),
            "unavailable_hooks": sorted(self.unavailable_hooks),
            "coverage_fraction": self.coverage_fraction,
            "complete": self.complete,
            "registration_api": self.registration_api,
            "errors": dict(sorted(self.errors.items())),
        }

    def close(self) -> None:
        """Best-effort explicit unregistration, in reverse registration order."""

        while self._unregister:
            callback = self._unregister.pop()
            callback()

    def __enter__(self) -> "SdkHookRegistration":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _observed_version(registrar: Any) -> str | None:
    for attribute in ("sdk_version", "__version__", "version"):
        value = getattr(registrar, attribute, None)
        if isinstance(value, str):
            return value
    return None


def _registration_method(
    registrar: Any,
) -> tuple[str | None, Callable[[str, Callable[..., ContextManager[None]]], Any] | None]:
    for name in ("register_mcp_tax_hook", "register_hook"):
        method = getattr(registrar, name, None)
        if callable(method):
            return name, method
    return None, None


def _context_factory(
    accumulator: McpMessageAccumulator, spec: SdkHookSpec
) -> Callable[..., ContextManager[None]]:
    def factory(**metadata: Any) -> ContextManager[None]:
        allowed = {
            "message_id",
            "process_role",
            "bytes",
            "bytes_in",
            "bytes_out",
            "count",
            "provenance",
        }
        unknown = set(metadata) - allowed
        if unknown:
            raise TypeError(
                f"unsupported hook metadata for {spec.name}: {sorted(unknown)}"
            )
        return mcp_timed(
            spec.category,
            accumulator=accumulator,
            message_id=metadata.get("message_id"),
            process_role=metadata.get("process_role"),
            bytes=metadata.get("bytes", 0),
            bytes_in=metadata.get("bytes_in", 0),
            bytes_out=metadata.get("bytes_out", 0),
            count=metadata.get("count", 1),
            provenance=metadata.get("provenance", f"sdk_hook:{spec.name}"),
        )

    return factory


def register_sdk_hooks(
    registrar: Any,
    *,
    accumulator: McpMessageAccumulator,
    expected_version: str,
    sdk_name: str | None = None,
    hook_specs: Iterable[SdkHookSpec] = DEFAULT_HOOK_SPECS,
) -> SdkHookRegistration:
    """Register only explicit hooks on an exactly matching SDK version.

    Failure is represented as zero/partial coverage rather than fabricated
    attribution. The returned coverage is also embedded in the endpoint ledger.
    """

    specs = tuple(hook_specs)
    name = sdk_name or str(getattr(registrar, "sdk_name", registrar.__class__.__name__))
    observed_version = _observed_version(registrar)
    registration = SdkHookRegistration(
        sdk_name=name,
        expected_version=expected_version,
        observed_version=observed_version,
        requested_hooks=len(specs),
    )
    if observed_version != expected_version:
        registration.unavailable_hooks = [spec.name for spec in specs]
        registration.errors["version"] = (
            f"expected exact SDK version {expected_version!r}, "
            f"observed {observed_version!r}"
        )
        accumulator.record_sdk_coverage(registration.as_dict())
        return registration

    api_name, register = _registration_method(registrar)
    registration.registration_api = api_name
    if register is None:
        registration.unavailable_hooks = [spec.name for spec in specs]
        registration.errors["registration_api"] = (
            "SDK exposes no explicit register_mcp_tax_hook/register_hook API"
        )
        accumulator.record_sdk_coverage(registration.as_dict())
        return registration

    supported = getattr(registrar, "supported_hooks", None)
    supported_set = set(supported) if supported is not None else None
    for spec in specs:
        if supported_set is not None and spec.name not in supported_set:
            registration.unavailable_hooks.append(spec.name)
            continue
        try:
            result = register(spec.name, _context_factory(accumulator, spec))
        except (AttributeError, NotImplementedError, TypeError, ValueError) as exc:
            registration.unavailable_hooks.append(spec.name)
            registration.errors[spec.name] = f"{type(exc).__name__}: {exc}"
            continue
        if result is False:
            registration.unavailable_hooks.append(spec.name)
            continue
        registration.registered_hooks.append(spec.name)
        if callable(result):
            registration._unregister.append(result)

    accumulator.record_sdk_coverage(registration.as_dict())
    return registration


def coverage_from_ledger(
    accumulator: McpMessageAccumulator,
) -> tuple[Mapping[str, Any], ...]:
    """Expose immutable snapshots of all registration attempts."""

    return tuple(dict(item) for item in accumulator.sdk_coverage)
