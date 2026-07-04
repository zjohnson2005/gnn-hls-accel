"""Generate OE HLS config variants (stretch: Phase C3)."""

import argparse
import csv
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "hls" / "oe_hls_config.h"
OUT = Path(__file__).resolve().parents[1] / "characterization" / "out" / "phase2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT / "variants.csv")
    args = parser.parse_args()

    rows = []
    for cap in (4, 8, 16):
        for max_nodes in (1024, 4096, 16384):
            for banks in (1, 2, 4):
                rows.append(
                    {
                        "cap": cap,
                        "max_nodes": max_nodes,
                        "banks": banks,
                        "fmax_mhz": "",
                        "lut": "",
                        "bram": "",
                        "cycles": "",
                        "note": "run csynth on server per variant",
                    }
                )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote {0} ({1} variants)".format(args.output, len(rows)))


if __name__ == "__main__":
    main()
