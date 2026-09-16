from __future__ import annotations

import pytest

from apu_characterization.tlp01.contracts import validate_lock
from apu_characterization.tlp01.protocol_lock import (
    build_locked_protocol,
    write_locked_protocol,
)


def test_lock_is_immutable(tmp_path) -> None:
    manifest = {
        "tasks": [
            {
                "task_id": "MT-01",
                "rationale": "three independent sources",
                "class": "FO",
            }
        ]
    }
    locked = build_locked_protocol(s2_task_manifest=manifest)
    assert locked["status"] == "locked"
    assert not validate_lock(locked)
    path = tmp_path / "protocol_tlp01_v1.locked.json"
    write_locked_protocol(locked, path)
    write_locked_protocol(locked, path)  # identical rewrite OK
    mutated = dict(locked)
    mutated["claim_under_test"] = "mutated"
    with pytest.raises(FileExistsError):
        write_locked_protocol(mutated, path)
