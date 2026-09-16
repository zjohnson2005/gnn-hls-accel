from __future__ import annotations

from dataclasses import replace

from apu_characterization.cap01.contracts import (
    CandidateRecord,
    CellCoordinates,
    PoolMetadata,
    enumerate_primary_matrix,
)


def _pool(task_id: str = "MATH-001", count: int = 8) -> PoolMetadata:
    return PoolMetadata(
        task_id=task_id,
        generation_model="test-model",
        temperature=0.7,
        prompt_template_sha256="a" * 64,
        candidates=tuple(
            CandidateRecord(
                candidate_id=f"{task_id}-{index}",
                task_id=task_id,
                ordinal=index,
                content=str(index),
                prompt_tokens=10,
                completion_tokens=1,
            )
            for index in range(count)
        ),
    )


def test_seed_order_is_stable_and_task_specific() -> None:
    pool = _pool()
    assert pool.seed_order(3) == pool.seed_order(3)
    assert pool.seed_order(3) != pool.seed_order(4)
    assert pool.seed_order(3) != _pool("MATH-002").seed_order(3)


def test_pool_hash_changes_with_candidate_content() -> None:
    pool = _pool()
    changed = replace(
        pool,
        candidates=(
            replace(pool.candidates[0], content="changed"),
            *pool.candidates[1:],
        ),
    )
    assert pool.pool_sha256() != changed.pool_sha256()


def test_primary_matrix_has_180_cells() -> None:
    cells = enumerate_primary_matrix()
    assert len(cells) == 3 * 6 * 2 * 5
    assert len({cell.cell_id for cell in cells}) == len(cells)
    assert CellCoordinates("langgraph", 5, 10000, 0).cell_id in {
        cell.cell_id for cell in cells
    }
