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
        estimated_clock_ns=None,
    ):
        self.top = top
        self.clock_period_ns = clock_period_ns
        self.estimated_clock_ns = estimated_clock_ns
        self.estimated_fmax_mhz = estimated_fmax_mhz
        self.top_latency_min = top_latency_min
        self.top_latency_max = top_latency_max
        self.modules = modules
        self.report_path = report_path

    @property
    def is_measured(self):
        return self.estimated_fmax_mhz is not None or self.estimated_clock_ns is not None

    @property
    def clock_mhz(self):
        if self.estimated_fmax_mhz and self.estimated_fmax_mhz > 0:
            return self.estimated_fmax_mhz
        if self.estimated_clock_ns and self.estimated_clock_ns > 0:
            return 1000.0 / self.estimated_clock_ns
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
            "estimated_clock_ns": self.estimated_clock_ns,
            "estimated_fmax_mhz": self.estimated_fmax_mhz,
            "top_latency_min": self.top_latency_min,
            "top_latency_max": self.top_latency_max,
            "modules": self.modules,
            "report_path": self.report_path,
            "is_measured": self.is_measured,
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
            estimated_clock_ns=data.get("estimated_clock_ns"),
        )


def _parse_int(s):
    if s is None:
        return None
    s = s.strip()
    if not s or s in ("-", "?"):
        return None
    m = re.match(r"^(\d+)", s)
    if not m:
        return None
    return int(m.group(1))


def _parse_float_ns(s):
    if s is None:
        return None
    s = s.strip()
    m = re.search(r"([\d.]+)\s*ns", s, re.I)
    if not m:
        return None
    return float(m.group(1))


def _fmax_from_period_ns(period_ns):
    if period_ns and period_ns > 0:
        return 1000.0 / period_ns
    return None


def _parse_top_name(text, fallback):
    patterns = (
        r"==\s*Vitis HLS Report for\s+'([^']+)'",
        r"\+ Top:\s*(\S+)",
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return fallback


def _parse_timing(text):
    target_ns = estimated_ns = None

    m_clk = re.search(
        r"\|\s*ap_clk\s*\|\s*([\d.]+\s*ns)\s*\|\s*([\d.]+\s*ns)\s*\|",
        text,
        re.I,
    )
    if m_clk:
        target_ns = _parse_float_ns(m_clk.group(1))
        estimated_ns = _parse_float_ns(m_clk.group(2))
        return target_ns, estimated_ns

    m_target = re.search(r"\|\s*Target\s*\|\s*([\d.]+\s*ns?)\s*\|", text, re.I)
    if m_target:
        target_ns = _parse_float_ns(m_target.group(1))
        if target_ns is None:
            m_num = re.search(r"([\d.]+)", m_target.group(1))
            if m_num:
                target_ns = float(m_num.group(1))

    m_est = re.search(r"\|\s*Estimated\s*\|\s*([\d.]+\s*ns?)\s*\|", text, re.I)
    if m_est:
        estimated_ns = _parse_float_ns(m_est.group(1))
        if estimated_ns is None:
            m_num = re.search(r"([\d.]+)", m_est.group(1))
            if m_num:
                estimated_ns = float(m_num.group(1))

    return target_ns, estimated_ns


def _parse_fmax(text, estimated_ns):
    patterns = (
        r"\*{0,4}\s*Estimated\s+Fmax\s*:\s*([\d.]+)\s*MHz",
        r"Estimated\s+Fmax\s*\|\s*([\d.]+)\s*MHz",
    )
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return float(m.group(1))
    return _fmax_from_period_ns(estimated_ns)


def _parse_top_latency(text):
    in_latency = False
    past_header = False
    for line in text.splitlines():
        if "+ Latency:" in line:
            in_latency = True
            past_header = False
            continue
        if not in_latency:
            continue
        if line.strip().startswith("+ Detail:"):
            break
        if "| min | max |" in line or "|     min   |     max   |" in line:
            past_header = True
            continue
        if past_header and line.strip().startswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0] and not cols[0].startswith("="):
                lat_min = _parse_int(cols[0])
                lat_max = _parse_int(cols[1])
                if lat_min is not None or lat_max is not None:
                    return lat_min, lat_max
    return None, None


def _parse_loop_modules(text):
    modules = []
    in_loops = False
    for line in text.splitlines():
        if "* Loop:" in line:
            in_loops = True
            continue
        if in_loops and line.strip().startswith("="):
            break
        if in_loops and line.strip().startswith("+---"):
            continue
        if in_loops and line.strip().startswith("|") and "Loop Name" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0] and not cols[0].startswith("="):
                latency_text = cols[1] if len(cols) > 1 else ""
                lat_parts = re.findall(r"\d+", latency_text)
                lat_min = int(lat_parts[0]) if lat_parts else None
                lat_max = int(lat_parts[-1]) if lat_parts else lat_min
                modules.append(
                    {
                        "name": cols[0],
                        "latency_min": lat_min,
                        "latency_max": lat_max,
                        "ii": _parse_int(cols[3]) if len(cols) > 3 else None,
                        "trip_count": cols[4] if len(cols) > 4 else None,
                    }
                )
        if in_loops and (
            line.strip().startswith("+ Utilization")
            or line.strip().startswith("== Utilization")
        ):
            break
    return modules


def parse_csynth_xml(path):
    import xml.etree.ElementTree as ET

    root = ET.parse(str(path)).getroot()
    top = path.stem.replace("_csynth", "")

    target_node = root.find("./UserAssignments/TargetClockPeriod")
    target_ns = float(target_node.text) if target_node is not None and target_node.text else None

    perf = root.find("./PerformanceEstimates")
    if perf is None:
        return None

    est_node = perf.find("./SummaryOfTimingAnalysis/EstimatedClockPeriod")
    estimated_ns = float(est_node.text) if est_node is not None and est_node.text else None

    best = perf.find("./SummaryOfOverallLatency/Best-caseLatency")
    worst = perf.find("./SummaryOfOverallLatency/Worst-caseLatency")
    top_lat_min = int(best.text) if best is not None and best.text and best.text.isdigit() else None
    top_lat_max = int(worst.text) if worst is not None and worst.text and worst.text.isdigit() else None

    fmax = _fmax_from_period_ns(estimated_ns)

    return CsynthReport(
        top=top,
        clock_period_ns=target_ns,
        estimated_clock_ns=estimated_ns,
        estimated_fmax_mhz=fmax,
        top_latency_min=top_lat_min,
        top_latency_max=top_lat_max,
        modules=[],
        report_path=str(path),
    )


def parse_csynth_rpt(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    top = _parse_top_name(text, path.stem.replace("_csynth", ""))
    target_ns, estimated_ns = _parse_timing(text)
    fmax = _parse_fmax(text, estimated_ns)
    top_lat_min, top_lat_max = _parse_top_latency(text)
    modules = _parse_loop_modules(text)

    return CsynthReport(
        top=top,
        clock_period_ns=target_ns,
        estimated_clock_ns=estimated_ns,
        estimated_fmax_mhz=fmax,
        top_latency_min=top_lat_min,
        top_latency_max=top_lat_max,
        modules=modules,
        report_path=str(path),
    )


def parse_csynth_report(path):
    path = Path(path)
    xml_path = path.with_name(path.name.replace("_csynth.rpt", "_csynth.xml"))
    if xml_path.exists():
        try:
            report = parse_csynth_xml(xml_path)
            if report is not None:
                report.report_path = str(path)
                if report.is_measured:
                    return report
        except Exception:
            pass
    return parse_csynth_rpt(path)


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


def load_or_parse(report_path=None, force=False):
    cached = OUT_DIR / "csynth_scatter.json"

    if report_path is None and cached.exists() and not force:
        data = json.loads(cached.read_text(encoding="utf-8"))
        report = CsynthReport.from_dict(data)
        if report.is_measured:
            return report

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
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        fixture = Path(__file__).resolve().parent / "fixtures" / "sample_scatter_csynth.rpt"
        report = parse_csynth_report(fixture)
        assert report.top == "oe_hls_scatter_kernel", report.top
        assert report.estimated_fmax_mhz == 415.63, report.estimated_fmax_mhz
        assert report.top_latency_min == 9, report.top_latency_min
        print("self-test OK")
        return 0

    report = load_or_parse(args.report, force=args.report is not None)
    if report is None:
        print("No csynth report found. Run run_hls_scatter.tcl on the Vitis box first.")
        return 1

    print(json.dumps(report.to_dict(), indent=2))
    if not report.is_measured:
        print("\nWARNING: could not parse timing from report; using default clock.")
    print(
        "\nScatter @ fan-out=2: {0:.4f} us ({1:.0f} cycles @ {2:.1f} MHz)".format(
            report.scatter_us(2),
            report.scatter_us(2) / report.us_per_cycle(),
            report.clock_mhz,
        )
    )
    return 0 if report.is_measured else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
