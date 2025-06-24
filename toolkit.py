# toolkit.py – Three independent helpers for the pipeline
"""
Phase‑1, Phase‑2, Phase‑3 utilities extracted from the bigger PoC so you can
mix‑and‑match them from your own scripts (or call them from PyCharm Run
Configurations).

* **InteractionRunner** – spins up the multi‑agent chat and stores the raw tee
  log (no parsing / file‑writing, only the conversation).
* **LogToMarkdown** – converts any `run_*.log` produced above into a clean
  `demo_output.md` that can later be replayed deterministically.
* **MarkdownToJava** – scans the markdown for Java code or JSON payloads and
  materialises proper `*.java` files under `extracted_src/`.

Each class exposes a single `run()` / `convert()` / `extract()` static method
so you can call them from a notebook, CLI wrapper, or unit test.
"""

from __future__ import annotations

import json, re, sys, datetime, subprocess
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Phase‑1 – generate the conversation (delegates to the original runner)
# ---------------------------------------------------------------------------

# toolkit.py  (only the run-phase changed)

class InteractionRunner:
    @staticmethod
    def run(feature: str) -> None:
        """
        Phase-1 – spawn the legacy script and let it print / tee the conversation.
        We DON'T care about its exit code – even a failure leaves a complete run_*.log.
        """
        script   = Path(__file__).with_name("multi_agent_boilerplate_poc.py")
        cmd = [sys.executable, str(script), "run", f'"{feature}"']

        print("[runner] launching:", " ".join(cmd))
        # --------- just drop 'check=True' -------------
        proc = subprocess.run(cmd, capture_output=True, text=True)  # ← check=False by default
        if proc.returncode != 0:
            print(f"[runner] inner script exited {proc.returncode} – ignoring, log is still there")
            print("[runner] stderr snapshot ↓↓↓\n", proc.stderr[:800], "\n···")

# ---------------------------------------------------------------------------
# Phase‑2 – log ‑> markdown
# ---------------------------------------------------------------------------

class LogToMarkdown:
    """Convert a tee-log into the minimal `demo_output.md` format."""
    HEADER_RE = re.compile(r"^Next speaker:\s*(.+)$")

    @staticmethod
    def convert(log_path: Path, md_out: Path):
        raw = log_path.read_text("utf-8", errors="ignore")
        parts = []
        sender, buf = None, []

        for line in raw.splitlines():
            m = LogToMarkdown.HEADER_RE.match(line.strip())
            if m:                                     # ───── new speaker header
                if sender and buf:
                    parts.append((sender, "\n".join(buf).rstrip()))
                sender, buf = m.group(1).strip(), []
            else:
                buf.append(line)
        if sender and buf:
            parts.append((sender, "\n".join(buf).rstrip()))

        md_out.write_text(
            "\n\n".join(f"### {s}\n\n{b}\n" for s, b in parts if b.strip()),
            "utf-8"
        )
        print(f"[LogToMarkdown] wrote {md_out}")

# ---------------------------------------------------------------------------
# Phase‑3 – markdown ‑> Java source tree
# ---------------------------------------------------------------------------

class MarkdownToJava:
    """Extract Java classes from a conversation markdown file."""

    DEST_ROOT = Path("extracted_src")

    MD_FENCE = re.compile(r"```java\s+(?P<body>.*?)```", re.S | re.I)
    JSON_FENCE = re.compile(r"```(?:json)?\s*(?P<json>\{.*?\})\s*```", re.S | re.I)

    @staticmethod
    def _path_from_package(code: str, cls_name: str) -> Path:
        m = re.search(r"^\s*package\s+([\w.]+);", code, re.M)
        if m:
            return Path(m.group(1).replace(".", "/")) / f"{cls_name}.java"
        return Path(f"{cls_name}.java")

    @classmethod
    def _write(cls, rel_path: Path, code: str):
        dest = cls.DEST_ROOT / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code.rstrip() + "\n", "utf-8")
        print(f"  ✔ {dest.relative_to(cls.DEST_ROOT)}")

    @classmethod
    def extract(cls, md_file: Path):
        cls.DEST_ROOT.mkdir(exist_ok=True)
        text = md_file.read_text("utf-8")

        # 1) explicit ```java``` fences
        for body in cls.MD_FENCE.findall(text):
            m_cls = re.search(r"\bclass\s+([A-Za-z_][\w]*)", body)
            if not m_cls:
                continue
            cls_name = m_cls.group(1)
            cls._write(cls._path_from_package(body, cls_name), body)

        # 2) JSON payloads with "javaClass"
        for jf in cls.JSON_FENCE.findall(text):
            try:
                data = json.loads(jf)
            except json.JSONDecodeError:
                continue
            jc = data.get("javaClass")
            if not jc:
                continue
            path = Path(jc.get("path", jc.get("name", "UnnamedClass.java")))
            # look for the next java fence as the implementation
            tail = text.split(jf, 1)[1]
            code_match = cls.MD_FENCE.search(tail)
            if code_match:
                code = code_match.group("body")
            else:
                # fallback stub
                cls_name = path.stem
                pkg_line = f"package {path.parent.as_posix().replace('/', '.')};\n\n" if path.parent != Path('.') else ""
                code = f"{pkg_line}public class {cls_name} {{\n    // TODO: implement\n}}"
            cls._write(path, code)
        print(f"[MarkdownToJava] output root → {cls.DEST_ROOT.resolve()}")

# ---------------------------------------------------------------------------
# CLI façade
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="two‑phase + extract helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("run", help="Phase‑1: generate interaction log")
    p1.add_argument("feature", help="e.g. 'Add JWT login'")

    p2 = sub.add_parser("log2md", help="Phase‑2: convert run_*.log → demo_output.md")
    p2.add_argument("log_file", type=Path)
    p2.add_argument("md_out", type=Path)

    p3 = sub.add_parser("md2java", help="Phase‑3: extract Java classes from markdown")
    p3.add_argument("markdown", type=Path)

    args = ap.parse_args()

    if args.cmd == "run":
        InteractionRunner.run(args.feature)
    elif args.cmd == "log2md":
        LogToMarkdown.convert(args.log_file, args.md_out)
    elif args.cmd == "md2java":
        MarkdownToJava.extract(args.markdown)
