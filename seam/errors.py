"""Exception hierarchy for SEAM.

Every failure mode the harness can hit has a named type. This exists so that nothing is ever
caught as a bare ``Exception`` and quietly discarded (spec §9.6): a caller that wants to tolerate
a specific failure must name it, and naming it makes the tolerance reviewable.
"""

from __future__ import annotations

__all__ = [
    "ConfigError",
    "DirtyTreeError",
    "GitError",
    "ManifestValidationError",
    "ProvenanceError",
    "RawStoreError",
    "RunSealedError",
    "SeamError",
    "TopologyNotVerifiedError",
    "TopologyVerificationError",
]


class SeamError(Exception):
    """Base class for every SEAM error."""


class ConfigError(SeamError):
    """A configuration file is missing, malformed, or internally inconsistent."""


class GitError(SeamError):
    """Git state could not be determined.

    Raised rather than defaulted. A manifest with an unknown ``git_sha`` is not auditable, so an
    unavailable git is a hard failure and never a ``null`` field.
    """


class DirtyTreeError(SeamError):
    """The working tree has uncommitted changes and ``--allow-dirty`` was not passed.

    Spec §7/M1: a run on a dirty tree is not reproducible, because ``git_sha`` does not describe
    the code that actually executed.
    """


class ManifestValidationError(SeamError):
    """A manifest failed JSON-Schema validation."""


class ProvenanceError(SeamError):
    """A declared provenance artifact is missing or unreadable.

    Blueprint §5.2 requires every run to pin the provenance snapshot it relied on, so a missing
    artifact invalidates the run rather than degrading it.
    """


class TopologyVerificationError(SeamError):
    """Empirical P/LP-E verification ran but did not produce a clean, expected result."""


class TopologyNotVerifiedError(SeamError):
    """An affinity list was requested but the platform config carries no verified mapping.

    Spec §4 requires the verified mapping to be asserted on every run. Guessing the mapping would
    silently answer open question 4 with an assumption.
    """


class RawStoreError(SeamError):
    """A ``raw/`` invariant was violated."""


class RunSealedError(RawStoreError):
    """An attempt was made to write into a run directory that is already sealed.

    This is the write-once guard (spec §9.1, blueprint §5.3). Raised on *attempt*, before any
    bytes are written.
    """
