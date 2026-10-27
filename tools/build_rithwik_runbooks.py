"""Task BS: build the two Rithwik runbook folders, their README PDFs and zips (Mac side).

Sources (committed): tools/rithwik_runbooks/{common.ps1, rtx4070.ps1, evo_x2.ps1, collect.ps1,
README_rtx4070.md, README_evo_x2.md}. Each run.ps1 = the machine script with the line
"#@@COMMON@@" replaced by common.ps1; collect.ps1 gets the machine name. Output (not in the repo):

  <out>/seam_xrt_<machine>/{README.md, README.pdf, run.ps1, collect.ps1}
  <out>/seam_xrt_<machine>_runbook.zip     (the folder, for sending)
  <out>/seam_xrt_<machine>_README.pdf      (the README alone, for sending)
  <out>/MANIFEST.sha256

The PDF is printed by headless Google Chrome from a minimal Markdown -> HTML rendering (headings,
paragraphs, lists, tables, inline code, bold). Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "rithwik_runbooks"
DEFAULT_OUT = Path.home() / "seam_closeout_1013" / "rithwik_runbooks"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
COMMON_MARK = "#@@COMMON@@"
MACHINE_MARK = "@@MACHINE@@"
ZIP_DATE = (2026, 10, 26, 0, 0, 0)  # fixed timestamp so the zip bytes depend only on content

MACHINES = {
    "rtx4070": {"script": "rtx4070.ps1", "readme": "README_rtx4070.md"},
    "evo-x2": {"script": "evo_x2.ps1", "readme": "README_evo_x2.md"},
}

CSS = """
body { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 9.6pt; line-height: 1.32;
       color: #111; margin: 0; }
h1 { font-size: 14pt; margin: 0 0 6pt 0; }
h2 { font-size: 11pt; margin: 10pt 0 4pt 0; }
p { margin: 4pt 0; }
ul, ol { margin: 3pt 0 3pt 16pt; padding: 0; }
li { margin: 1.5pt 0; }
code { font-family: 'Courier New', Courier, monospace; font-size: 8.4pt; background: #f1f1f1; padding: 0 2px; }
table { border-collapse: collapse; margin: 4pt 0; }
th, td { border: 1px solid #999; padding: 2pt 5pt; text-align: left; font-size: 8.8pt; }
th { background: #eaeaea; }
@page { size: Letter; margin: 0.55in 0.6in; }
"""


def build_run_script(machine: str) -> str:
    main = (SRC / MACHINES[machine]["script"]).read_text(encoding="ascii")
    common = (SRC / "common.ps1").read_text(encoding="ascii")
    if main.count(COMMON_MARK) != 1:
        raise ValueError(f"{machine}: expected exactly one {COMMON_MARK} line")
    return main.replace(COMMON_MARK, common.rstrip("\n"))


def build_collect(machine: str) -> str:
    text = (SRC / "collect.ps1").read_text(encoding="ascii")
    if MACHINE_MARK not in text:
        raise ValueError(f"collect.ps1 has no {MACHINE_MARK}")
    return text.replace(MACHINE_MARK, machine)


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)


def markdown_to_html(md: str, title: str) -> str:
    """Minimal renderer for the two READMEs (the subset they use)."""
    lines = md.splitlines()
    body: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("## "):
            body.append(f"<h2>{_inline(ln[3:])}</h2>")
            i += 1
        elif ln.startswith("# "):
            body.append(f"<h1>{_inline(ln[2:])}</h1>")
            i += 1
        elif ln.startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, rest = rows[0], rows[1:]
            body.append("<table><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
            body.extend(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rest
            )
            body.append("</table>")
        elif re.match(r"^(\s*)(-|\d+\.) ", ln):
            ordered = bool(re.match(r"^\d+\. ", ln))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            subs: dict[int, list[str]] = {}
            while i < len(lines) and lines[i].strip():
                cur = lines[i]
                m = re.match(r"^(-|\d+\.) (.*)$", cur)
                sub = re.match(r"^\s+- (.*)$", cur)
                if m:
                    items.append(m.group(2))
                elif sub and items:
                    subs.setdefault(len(items) - 1, []).append(sub.group(1))
                elif items and len(items) - 1 in subs:
                    subs[len(items) - 1][-1] += " " + cur.strip()
                elif items:
                    items[-1] += " " + cur.strip()
                i += 1
            rendered = []
            for k, t in enumerate(items):
                inner = "".join(f"<li>{_inline(x)}</li>" for x in subs.get(k, []))
                rendered.append(
                    f"<li>{_inline(t)}" + (f"<ul>{inner}</ul>" if inner else "") + "</li>"
                )
            body.append(f"<{tag}>" + "".join(rendered) + f"</{tag}>")
        else:
            para: list[str] = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not lines[i].startswith(("#", "|"))
                and not re.match(r"^(-|\d+\.) ", lines[i])
            ):
                para.append(lines[i].strip())
                i += 1
            body.append(f"<p>{_inline(' '.join(para))}</p>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
        + "\n".join(body)
        + "</body></html>"
    )


def print_pdf(html_text: str, pdf_path: Path, chrome: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "readme.html"
        src.write_text(html_text, encoding="utf-8")
        cmd = [
            str(chrome),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={td}/profile",
            f"--print-to-pdf={pdf_path}",
            src.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Chrome wrote no PDF at {pdf_path}")


def pdf_pages(pdf_path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_path.read_bytes()))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_zip(folder: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo(
                    f"{folder.name}/{p.relative_to(folder).as_posix()}", ZIP_DATE
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, p.read_bytes())


def build(out: Path, chrome: Path, make_pdf: bool) -> list[tuple[str, Path]]:
    out.mkdir(parents=True, exist_ok=True)
    made: list[tuple[str, Path]] = []
    for machine, spec in MACHINES.items():
        folder = out / f"seam_xrt_{machine}"
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        readme = (SRC / spec["readme"]).read_text(encoding="ascii")
        (folder / "README.md").write_text(readme, encoding="ascii")
        (folder / "run.ps1").write_text(build_run_script(machine), encoding="ascii")
        (folder / "collect.ps1").write_text(build_collect(machine), encoding="ascii")
        if make_pdf:
            title = readme.splitlines()[0].lstrip("# ").strip()
            print_pdf(markdown_to_html(readme, title), folder / "README.pdf", chrome)
            pdf_out = out / f"seam_xrt_{machine}_README.pdf"
            shutil.copyfile(folder / "README.pdf", pdf_out)
            made.append((f"pdf pages={pdf_pages(pdf_out)}", pdf_out))
        zip_path = out / f"seam_xrt_{machine}_runbook.zip"
        if zip_path.exists():
            zip_path.unlink()
        write_zip(folder, zip_path)
        made.append(("zip", zip_path))
        for name in ("run.ps1", "collect.ps1"):
            made.append(("script", folder / name))
    manifest = out / "MANIFEST.sha256"
    manifest.write_text(
        "".join(f"{sha256(p)}  {p.relative_to(out)}\n" for _, p in made), encoding="ascii"
    )
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--chrome", type=Path, default=CHROME)
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args(argv)
    made = build(args.out, args.chrome, not args.no_pdf)
    for kind, p in made:
        print(f"{kind:14s} {p}  {p.stat().st_size} B  sha256 {sha256(p)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
