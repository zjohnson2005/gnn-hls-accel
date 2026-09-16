from __future__ import annotations

from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.predictor import evaluate_predictor, split_sessions


def test_predictor_split_and_eval_smoke() -> None:
    sessions = [
        make_synthetic_parallel_session(
            session_id=f"syn-FO-s{seed}", seed=seed, width=4
        )
        for seed in range(5)
    ]
    train, test = split_sessions(sessions)
    assert train and test
    metrics = evaluate_predictor(train, test)
    assert "FO" in metrics
    assert 0.0 <= metrics["FO"]["top1_accuracy"] <= 1.0
