"""Parse Vitis HLS csynth reports into structured latency/resource numbers."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
DEFAULT_CLOCK_MHZ = 300.0


@dataclass
class CsynthModule:
    name: str
    latency_min: int | None
    latency_max: int | None
    ii: int | None
    trip_count: str | None


@dataclass
class CsynthReport:
    top: str
    clock_period_ns: float | None
    estimated_fmax_mhz: float | None
    top_latency_min: int | None
    top_latency_max: int | None
    modules: list[CsynthModule]
    report_path: str

    @property
    def clock_mhz(self) -> float:
        if self.estimated_fmax_mhz and self.estimated_fmax_mhz > 0:
            return self.estimated_fmax_mhz
        if self.clock_period_ns and self.clock_period_ns > 0:
            return 1000.0 / self.clock_period_ns
        return DEFAULT_CLOCK_MHZ

    def us_per_cycle(self) -> float:
        return 1e6 / (self.clock_mhz * 1e6)

    def scatter_us(self, out_degree: int, *, batch_width: int = 1) -> float:
        """Analytic model from achieved II=1 loops (1 + ceil(deg/width) cycles)."""
        if batch_width <= 1:
            cycles = 1 + out_degree
        else:
            cycles = 1 + (out_degree + batch_width - 1) // batch_width
        return cycles * self.us_per_cycle()


def _parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip()
    if not s or s == "-":
        return None
    return int(s)


def parse_csynth_report(path: Path) -> CsynthReport:
    text = path.read_text(encoding="utf-8", errors="replace")
    top = path.stem.replace("_csynth", "")

    m_top = re.search(r"\+ Top:\s*(\S+)", text)
    if m_top:
        top = m_top.group(1)

    period = None
    m_period = re.search(r"\|\s*Target\s*\|\s*([\d.]+)\s*\|", text)
    if m_period:
        period = float(m_period.group(1))

    fmax = None
    m_fmax = re.search(r"Estimated\s+Fmax\s*:\s*([\d.]+)\s*MHz", text, re.I)
    if m_fmax:
        fmax = float(m_fmax.group(1))

    top_lat_min = top_lat_max = None
    m_lat = re.search(
        r"\|\s*Latency\s*\(cycles\)\s*\|\s*(\d+|-)\s*\|\s*(\d+|-)\s*\|",
        text,
    )
    if m_lat:
        top_lat_min = _parse_int(m_lat.group(1))
        top_lat_max = _parse_int(m_lat.group(2))

    modules: list[CsynthModule] = []
    in_fn_table = False
    for line in text.splitlines():
        if "+ Modules" in line or "| Name" in line and "Latency" in line:
            in_fn_table = True
            continue
        if in_fn_table and line.strip().startswith("+---"):
            continue
        if in_fn_table and line.strip().startswith("|") and "Name" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4 and cols[0] and not cols[0].startswith("="):
                modules.append(
                    CsynthModule(
                        name=cols[0],
                        latency_min=_parse_int(cols[1]),
                        latency_max=_parse_int(cols[2]),
                        ii=_parse_int(cols[3]) if len(cols) > 3 else None,
                        trip_count=cols[4] if len(cols) > 4 else None,
                    )
                )
        if in_fn_table and line.strip() == "":
            in_fn_table = False

    return CsynthReport(
        top=top,
        clock_period_ns=period,
        estimated_fmax_mhz=fmax,
        top_latency_min=top_lat_min,
        top_latency_max=top_lat_max,
        modules=modules,
        report_path=str(path),
    )


def find_csynth_reports(search_roots: list[Path] | None = None) -> list[Path]:
    roots = search_roots or [
        OE_ROOT.parent / "oe_scatter_proj",
        OE_ROOT.parent / "oe_proj",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(root.glob("**/syn/report/*_csynth.rpt"))
    return sorted(set(found))


def load_or_parse(report_path: Path | None = None) -> CsynthReport | None:
    cached = OUT_DIR / "csynth_scatter.json"
    if report_path is None and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        return CsynthReport(**{k: data[k] for k in CsynthReport.__dataclass_fields__ if k in data})

    if report_path is None:
        reports = find_csynth_reports()
        if not reports:
            return None
        # Prefer scatter kernel project
        scatter = [p for p in reports if "scatter" in p.as_posix().lower()]
        report_path = scatter[0] if scatter else reports[-1]

    report = parse_csynth_report(report_path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Parse Vitis HLS csynth report")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    report = load_or_parse(args.report)
    if report is None:
        print("No csynth report found. Run run_hls_scatter.tcl on the Vitis box first.")
        return 1

    print(json.dumps(asdict(report), indent=2))
    print(
        f"\nScatter @ fan-out=2: {report.scatter_us(2):.4f} µs "
        f"({report.scatter_us(2) / report.us_per_cycle():.0f} cycles @ {report.clock_mhz:.0f} MHz)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
