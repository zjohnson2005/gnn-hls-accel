"""Parse Vitis HLS cosim reports for measured RTL latency."""

import json
import re
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"


class CosimReport(object):
    def __init__(
        self,
        top,
        rtl,
        status,
        latency_min,
        latency_max,
        interval_min,
        interval_max,
        fan_out,
        report_path,
    ):
        self.top = top
        self.rtl = rtl
        self.status = status
        self.latency_min = latency_min
        self.latency_max = latency_max
        self.interval_min = interval_min
        self.interval_max = interval_max
        self.fan_out = fan_out
        self.report_path = report_path

    @property
    def passed(self):
        if self.status is None:
            return False
        return self.status.lower() in ("pass", "passed")

    @property
    def latency_cycles(self):
        if self.latency_min is not None:
            return self.latency_min
        return self.latency_max

    def to_dict(self):
        return {
            "top": self.top,
            "rtl": self.rtl,
            "status": self.status,
            "latency_min": self.latency_min,
            "latency_max": self.latency_max,
            "latency_cycles": self.latency_cycles,
            "interval_min": self.interval_min,
            "interval_max": self.interval_max,
            "fan_out": self.fan_out,
            "report_path": self.report_path,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            top=data.get("top", ""),
            rtl=data.get("rtl"),
            status=data.get("status"),
            latency_min=data.get("latency_min"),
            latency_max=data.get("latency_max"),
            interval_min=data.get("interval_min"),
            interval_max=data.get("interval_max"),
            fan_out=data.get("fan_out", 2),
            report_path=data.get("report_path", ""),
        )


def _parse_int(s):
    if s is None:
        return None
    s = s.strip()
    if not s or s.upper() in ("-", "NA", "?"):
        return None
    m = re.match(r"^(\d+)", s)
    if not m:
        return None
    return int(m.group(1))


def parse_cosim_report(path, fan_out=2):
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    top = path.stem.replace("_cosim", "")

    m_top = re.search(r"==\s*Vitis HLS Report for\s+'([^']+)'", text)
    if m_top:
        top = m_top.group(1)

    rtl = status = None
    lat_min = lat_max = interval_min = interval_max = None

    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        if re.search(r"VHDL|Verilog", line, re.I) and "Status" not in line:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) >= 5:
                row_status = cols[1]
                if row_status.upper() in ("NA", "-", ""):
                    continue
                rtl = cols[0]
                status = row_status
                lat_min = _parse_int(cols[2])
                lat_max = _parse_int(cols[4]) if len(cols) > 4 else lat_min
                interval_min = _parse_int(cols[5]) if len(cols) > 5 else None
                interval_max = _parse_int(cols[7]) if len(cols) > 7 else None
                break

    if lat_min is None:
        in_latency = False
        past_header = False
        for line in text.splitlines():
            if "+ Latency:" in line:
                in_latency = True
                past_header = False
                continue
            if not in_latency:
                continue
            if "| min | max |" in line:
                past_header = True
                continue
            if past_header and line.strip().startswith("|"):
                cols = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cols) >= 2 and cols[0] and not cols[0].startswith("="):
                    lat_min = _parse_int(cols[0])
                    lat_max = _parse_int(cols[1])
                    break

    if status is None or status.upper() == "NA":
        if re.search(r"co-simulation finished:\s*PASS", text, re.I):
            status = "pass"
        elif re.search(r"Co-simulation\s+passed", text, re.I):
            status = "pass"
        else:
            m_status = re.search(r"Co-simulation\s+(passed|failed|Pass|Fail)", text, re.I)
            if m_status:
                status = "pass" if m_status.group(1).lower().startswith("p") else "fail"

    return CosimReport(
        top=top,
        rtl=rtl,
        status=status,
        latency_min=lat_min,
        latency_max=lat_max,
        interval_min=interval_min,
        interval_max=interval_max,
        fan_out=fan_out,
        report_path=str(path),
    )


def find_cosim_reports(search_roots=None):
    roots = search_roots or [
        OE_ROOT.parent / "oe_scatter_proj",
        OE_ROOT.parent / "oe_stream_proj",
        OE_ROOT.parent / "oe_proj",
    ]
    found = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(root.glob("**/sim/report/*_cosim.rpt"))
    return sorted(set(found))


def load_or_parse(report_path=None, fan_out=2, force=False):
    cached = OUT_DIR / "cosim_scatter.json"
    if report_path is None and cached.exists() and not force:
        data = json.loads(cached.read_text(encoding="utf-8"))
        report = CosimReport(
            top=data.get("top", ""),
            rtl=data.get("rtl"),
            status=data.get("status"),
            latency_min=data.get("latency_min"),
            latency_max=data.get("latency_max"),
            interval_min=data.get("interval_min"),
            interval_max=data.get("interval_max"),
            fan_out=data.get("fan_out", fan_out),
            report_path=data.get("report_path", ""),
        )
        if report.passed and report.latency_cycles is not None:
            return report

    if report_path is None:
        reports = find_cosim_reports()
        if not reports:
            return None
        scatter = [p for p in reports if "scatter" in p.as_posix().lower()]
        report_path = scatter[0] if scatter else reports[-1]

    report = parse_cosim_report(report_path, fan_out=fan_out)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Parse Vitis HLS cosim report")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--fan-out", type=int, default=2)
    parser.add_argument(
        "--transactions",
        type=int,
        default=None,
        help="Completions per invocation (streaming TB); records per-transaction cycles",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write parsed JSON here instead of the default cosim_scatter.json cache",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        fixture = Path(__file__).resolve().parent / "fixtures" / "sample_scatter_cosim.rpt"
        report = parse_cosim_report(fixture, fan_out=2)
        assert report.passed, report.status
        assert report.latency_cycles == 3, report.latency_cycles
        print("self-test OK")
        return 0

    if args.report is not None and args.out is not None:
        report = parse_cosim_report(args.report, fan_out=args.fan_out)
        data = report.to_dict()
        if args.transactions and report.latency_cycles is not None:
            data["transactions"] = args.transactions
            data["per_transaction_cycles"] = round(
                report.latency_cycles / float(args.transactions), 1
            )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(json.dumps(data, indent=2))
        if not report.passed:
            print("\nWARNING: cosim did not pass.")
            return 1
        return 0

    report = load_or_parse(args.report, fan_out=args.fan_out, force=args.report is not None)
    if report is None:
        print("No cosim report found. Enable cosim_design in run_hls_scatter.tcl.")
        return 1

    print(json.dumps(report.to_dict(), indent=2))
    if not report.passed:
        print("\nWARNING: cosim did not pass.")
        return 1
    if report.latency_cycles is None:
        print("\nWARNING: could not parse latency from cosim report.")
        return 1
    print(
        "\nCosim fan-out={0}: {1} RTL cycles (latency {2}-{3})".format(
            report.fan_out,
            report.latency_cycles,
            report.latency_min,
            report.latency_max,
        )
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
