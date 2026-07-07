#!/usr/bin/env bash
# Audit pipeline smoke on Linux/WSL without API key (scripted backend).
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")/.."

python3 -m apu_characterization.tests.test_resolution
python3 -m apu_characterization.experiments.replication_batch \
  --backend scripted --seeds 0,1 --search-locality remote --allow-dirty
