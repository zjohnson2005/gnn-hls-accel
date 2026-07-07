"""Generate deterministic fixtures (corpus + RAG matrix). Not committed as binaries."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import numpy as np

FIXTURES_DIR = Path(__file__).resolve().parent
CORPUS_PATH = FIXTURES_DIR / "corpus.txt"
VECTORS_PATH = FIXTURES_DIR / "vectors.npy"
META_PATH = FIXTURES_DIR / "fixtures_meta.json"

CORPUS_TARGET_BYTES = 50 * 1024 * 1024
NUM_VECTORS = 100_000
VECTOR_DIM = 384


# Topic word groups: paragraphs are built per topic so multi-word queries
# ("water cycle", "train speed") have realistic phrase locality.
TOPICS: dict[str, list[str]] = {
    "weather": [
        "weather", "rain", "snow", "sun", "cloud", "storm", "temperature",
        "wind", "forecast", "humidity", "season", "climate", "cold", "warm",
    ],
    "space": [
        "planet", "moon", "star", "orbit", "solar", "eclipse", "telescope",
        "galaxy", "rocket", "astronaut", "mars", "earth", "gravity", "light",
    ],
    "history": [
        "history", "revolution", "empire", "king", "queen", "war", "treaty",
        "ancient", "castle", "france", "rome", "century", "battle", "museum",
    ],
    "nature": [
        "plant", "tree", "leaf", "water", "cycle", "river", "ocean",
        "mountain", "forest", "animal", "bird", "fish", "flower", "soil",
    ],
    "food": [
        "bread", "flour", "recipe", "oven", "sugar", "salt", "butter",
        "cheese", "fruit", "vegetable", "dinner", "kitchen", "bake", "cook",
    ],
    "money": [
        "money", "bank", "interest", "price", "market", "stock", "save",
        "budget", "loan", "salary", "tax", "coin", "trade", "invest",
    ],
    "travel": [
        "train", "speed", "distance", "airport", "ticket", "journey", "map",
        "city", "bridge", "road", "hotel", "passport", "luggage", "station",
        "paris", "tokyo", "cairo", "attraction",
    ],
    "health": [
        "sleep", "exercise", "heart", "muscle", "vitamin", "doctor", "water",
        "energy", "brain", "healthy", "diet", "walk", "run", "rest",
    ],
    "garden": [
        "garden", "vegetable", "plant", "seed", "soil", "tomato", "frost",
        "harvest", "spring", "summer", "fall", "winter", "grow", "indoor",
    ],
    "cooking": [
        "cook", "boil", "egg", "simmer", "onion", "pasta", "chop", "cup",
        "recipe", "lesson", "pan", "stove", "heat", "mix",
    ],
    "party": [
        "party", "birthday", "theme", "kids", "fun", "snack", "juice",
        "schedule", "game", "balloon", "cake", "gift", "invite", "plan",
    ],
}


def _topic_paragraph(seed: int) -> str:
    rng = np.random.default_rng(seed)
    topic_names = sorted(TOPICS.keys())
    topic = topic_names[int(rng.integers(0, len(topic_names)))]
    words = TOPICS[topic]
    n = int(rng.integers(80, 200))
    picked = rng.choice(words, size=n, replace=True)
    return " ".join(picked) + "\n\n"


def generate_corpus(path: Path = CORPUS_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size >= CORPUS_TARGET_BYTES * 0.99:
        data = path.read_bytes()
        return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    with path.open("w", encoding="utf-8") as f:
        seed = 0
        while f.tell() < CORPUS_TARGET_BYTES:
            f.write(_topic_paragraph(seed))
            seed += 1

    data = path.read_bytes()
    if len(data) < CORPUS_TARGET_BYTES:
        with path.open("ab") as f:
            f.write(b"x" * (CORPUS_TARGET_BYTES - len(data)))
        data = path.read_bytes()

    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def generate_vectors(path: Path = VECTORS_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        arr = np.load(path, mmap_mode="r")
        if arr.shape == (NUM_VECTORS, VECTOR_DIM):
            raw = path.read_bytes()
            return {
                "path": str(path),
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

    rng = np.random.default_rng(42)
    # float32 unit-ish vectors for cosine similarity work
    mat = rng.standard_normal((NUM_VECTORS, VECTOR_DIM)).astype(np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    mat /= np.maximum(norms, 1e-6)
    np.save(path, mat)
    raw = path.read_bytes()
    return {
        "path": str(path),
        "shape": [NUM_VECTORS, VECTOR_DIM],
        "dtype": "float32",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def ensure_fixtures() -> dict:
    import json

    corpus_meta = generate_corpus()
    vectors_meta = generate_vectors()
    meta = {"corpus": corpus_meta, "vectors": vectors_meta}
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate apu_characterization fixtures")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.force:
        if CORPUS_PATH.is_file():
            CORPUS_PATH.unlink()
        if VECTORS_PATH.is_file():
            VECTORS_PATH.unlink()
    meta = ensure_fixtures()
    print(f"corpus: {meta['corpus']['bytes']} bytes")
    print(f"vectors: {meta['vectors']['shape']}")


if __name__ == "__main__":
    main()
