"""Parse Vitis HLS csynth reports into structured latency/resource numbers."""

import json
import re
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
DEFAULT_CLOCK_MHZ = 300.0


class CsynthReport(object):
    def __init__(
        self,
        top,
        clock_period_ns,
        estimated_fmax_mhz,
        top_latency_min,
        top_latency_max,
        modules,
        report_path,
    ):
        self.top = top
        self.clock_period_ns = clock_period_ns
        self.estimated_fmax_mhz = estimated_fmax_mhz
        self.top_latency_min = top_latency_min
        self.top_latency_max = top_latency_max
        self.modules = modules
        self.report_path = report_path

    @property
    def clock_mhz(self):
        if self.estimated_fmax_mhz and self.estimated_fmax_mhz > 0:
            return self.estimated_fmax_mhz
        if self.clock_period_ns and self.clock_period_ns > 0:
            return 1000.0 / self.clock_period_ns
        return DEFAULT_CLOCK_MHZ

    def us_per_cycle(self):
        return 1e6 / (self.clock_mhz * 1e6)

    def scatter_us(self, out_degree, batch_width=1):
        if batch_width <= 1:
            cycles = 1 + out_degree
        else:
            cycles = 1 + (out_degree + batch_width - 1) // batch_width
        return cycles * self.us_per_cycle()

    def to_dict(self):
        return {
            "top": self.top,
            "clock_period_ns": self.clock_period_ns,
            "estimated_fmax_mhz": self.estimated_fmax_mhz,
            "top_latency_min": self.top_latency_min,
            "top_latency_max": self.top_latency_max,
            "modules": self.modules,
            "report_path": self.report_path,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            top=data["top"],
            clock_period_ns=data.get("clock_period_ns"),
            estimated_fmax_mhz=data.get("estimated_fmax_mhz"),
            top_latency_min=data.get("top_latency_min"),
            top_latency_max=data.get("top_latency_max"),
            modules=data.get("modules", []),
            report_path=data.get("report_path", ""),
        )


def _parse_int(s):
    if s is None:
        return None
    s = s.strip()
    if not s or s == "-":
        return None
    return int(s)


def parse_csynth_report(path):
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

    modules = []
    in_fn_table = False
    for line in text.splitlines():
        if "+ Modules" in line or ("| Name" in line and "Latency" in line):
            in_fn_table = True
            continue
        if in_fn_table and line.strip().startswith("+---"):
            continue
        if in_fn_table and line.strip().startswith("|") and "Name" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4 and cols[0] and not cols[0].startswith("="):
                mod = {
                    "name": cols[0],
                    "latency_min": _parse_int(cols[1]),
                    "latency_max": _parse_int(cols[2]),
                    "ii": _parse_int(cols[3]) if len(cols) > 3 else None,
                    "trip_count": cols[4] if len(cols) > 4 else None,
                }
                modules.append(mod)
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


def find_csynth_reports(search_roots=None):
    roots = search_roots or [
        OE_ROOT.parent / "oe_scatter_proj",
        OE_ROOT.parent / "oe_proj",
    ]
    found = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(root.glob("**/syn/report/*_csynth.rpt"))
    return sorted(set(found))


def load_or_parse(report_path=None):
    cached = OUT_DIR / "csynth_scatter.json"
    if report_path is None and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        return CsynthReport.from_dict(data)

    if report_path is None:
        reports = find_csynth_reports()
        if not reports:
            return None
        scatter = [p for p in reports if "scatter" in p.as_posix().lower()]
        report_path = scatter[0] if scatter else reports[-1]

    report = parse_csynth_report(report_path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Parse Vitis HLS csynth report")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    report = load_or_parse(args.report)
    if report is None:
        print("No csynth report found. Run run_hls_scatter.tcl on the Vitis box first.")
        return 1

    print(json.dumps(report.to_dict(), indent=2))
    print(
        "\nScatter @ fan-out=2: {0:.4f} us ({1:.0f} cycles @ {2:.0f} MHz)".format(
            report.scatter_us(2),
            report.scatter_us(2) / report.us_per_cycle(),
            report.clock_mhz,
        )
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
