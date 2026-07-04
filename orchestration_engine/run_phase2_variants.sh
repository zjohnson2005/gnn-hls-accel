#!/usr/bin/env bash
# C3: csynth a subset of OE HLS config variants (cap / max_nodes / banks).
# Server-only for vitis_hls; --dry-run works locally to emit variants.csv only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

DRY=0
LIMIT=6
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --limit) LIMIT="$2"; shift 2 ;;
    *) echo "Usage: $0 [--dry-run] [--limit N]"; exit 1 ;;
  esac
done

python3 orchestration_engine/eval/gen_variants.py --output "$OUT/variants.csv"

if [[ "$DRY" -eq 1 ]]; then
  echo "Dry run: wrote $OUT/variants.csv only"
  exit 0
fi

source "$ROOT/orchestration_engine/hls_env.sh"

RESULTS="$OUT/variants_results.json"
echo "[" > "$RESULTS"

count=0
first=1
while IFS=, read -r cap max_nodes banks _rest; do
  [[ "$cap" == "cap" ]] && continue
  [[ "$count" -ge "$LIMIT" ]] && break

  PROJ="oe_var_${cap}_${max_nodes}_b${banks}"
  echo ""
  echo "=== C3 csynth cap=$cap max_nodes=$max_nodes banks=$banks -> $PROJ ==="

  rm -rf "$PROJ"
  vitis_hls -f orchestration_engine/run_hls_scatter_variant.tcl \
    -tclargs "$PROJ" "$cap" "$max_nodes" "$banks" || {
    echo "WARN: csynth failed for $PROJ" >&2
    count=$((count + 1))
    continue
  }

  RPT="$(find "$PROJ" -name 'oe_hls_scatter_stream_csynth.rpt' | head -1)"
  LAT=""
  FMAX=""
  if [[ -n "$RPT" ]]; then
    LAT="$(grep -m1 'Latency (cycles)' "$RPT" | awk '{print $3}' || true)"
    FMAX="$(grep -m1 'Estimated Fmax' "$RPT" | awk '{print $5}' || true)"
  fi

  sep=""
  [[ "$first" -eq 1 ]] || sep=","
  first=0
  printf '%s{"cap":%s,"max_nodes":%s,"banks":%s,"project":"%s","latency_min":"%s","fmax_mhz":"%s"}\n' \
    "$sep" "$cap" "$max_nodes" "$banks" "$PROJ" "${LAT:-?}" "${FMAX:-?}" >> "$RESULTS"
  count=$((count + 1))
done < "$OUT/variants.csv"

echo "]" >> "$RESULTS"
echo "Wrote $RESULTS ($count variants)"

python3 -m orchestration_engine.phase2_gate.gate_report --refresh
