# multi_agent_boilerplate_poc.py — **Java / Spring‑Boot single‑file PoC** (v1.0)
"""
Minimal, _working_ proof‑of‑concept that demonstrates:

1.  **Multi–agent conversation** (Product‑Manager → Architect → Coder → Reviewer)
2.  **Plain‑text tee logging** to `run_<timestamp>.log`
3.  **One JSON payload** returned by the *Coder* (exactly **one** Java class **+** a `pom.xml`)
4.  Heuristic writer that dumps the first Java file **and** `pom.xml` under `out_<timestamp>/`.

Two additional helper modes let you:
* **export‑log** – turn any `run_*.log` into a clean `demo_output.md` you can replay later.
* **messages** – parse such a markdown dump without calling an LLM at all.

> ⚠️ This is intentionally **small & opinionated**. It is _not_ a full scaffold generator –
> just enough to unblock demo pipelines and unit‑tests.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

# ---------------------------------------------------------------------------
# 0️⃣ Globals    ─────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

RUN_STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TEE_LOG   = Path(__file__).with_name(f"run_{RUN_STAMP}.log")

OLLAMA_URL = "http://localhost:11434/v1"
MODEL_NAME = "llama3.2:latest"   # must exist in `ollama list`

LLM = {
    "model":       MODEL_NAME,
    "base_url":    OLLAMA_URL,
    "api_key":     "ollama",  # dummy key – Ollama ignores it
    "temperature": 0.15,
    "max_tokens":  4096,
    "price":       [0.0, 0.0],
}

# ---------------------------------------------------------------------------
# 1️⃣ Tiny tee helper  ───────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

class _Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            try:
                s.write(data); s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass

sys.stdout = _Tee(sys.stdout, TEE_LOG.open("w", encoding="utf‑8"))
sys.stderr = sys.stdout
print(f"[DEBUG] tee logging to {TEE_LOG}\n")

# ---------------------------------------------------------------------------
# 2️⃣ Utility – extract JSON blocks  ─────────────────────────────────────────
# ---------------------------------------------------------------------------

def json_blocks(text: str) -> Iterable[str]:
    fence = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)
    yield from (m.group(1) for m in fence.finditer(text))
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        yield stripped

# ---------------------------------------------------------------------------
# 3️⃣ Writer – persist first Java file + pom  ────────────────────────────────
# ---------------------------------------------------------------------------

def write_first_file(messages: List[str]) -> Path:
    out_dir = Path(__file__).parent / f"out_{RUN_STAMP}"
    out_dir.mkdir(parents=True, exist_ok=True)

    for msg in messages:
        if not msg.strip():
            continue
        for chunk in json_blocks(msg):
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            files = data.get("files") if isinstance(data, dict) else None
            if not files:
                continue
            # pick first *.java otherwise first entry
            entry = next((f for f in files if f.get("path", "").endswith(".java")), files[0])
            dest = out_dir / Path(entry["path"].strip())
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(entry.get("content", "").rstrip() + "\n", "utf‑8")
            print(f"[DEBUG] wrote {dest.relative_to(out_dir)}")

            pom = next((f for f in files if f.get("path") == "pom.xml"), None)
            if pom:
                (out_dir / "pom.xml").write_text(pom.get("content", "").rstrip() + "\n", "utf‑8")
            return out_dir

    # nothing found → dump raw & fail
    Path("coder_raw_dump.txt").write_text("\n\n---\n\n".join(messages), "utf‑8")
    raise RuntimeError("Coder did not return a valid JSON payload. See coder_raw_dump.txt")

# ---------------------------------------------------------------------------
# 4️⃣ Agent builders  ────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def make_agents():
    pm = AssistantAgent("PM", llm_config=LLM, system_message=(
        "You are a pragmatic product‑manager. Rewrite the vague feature as bullet user‑stories + acceptance criteria. No code."))

    architect = AssistantAgent("Architect", llm_config=LLM, system_message=(
        "You are a senior Java architect. Produce a concise design (modules, deps) and finish with a Maven directory tree. No implementation code."))

    coder = AssistantAgent("Coder", llm_config=LLM, system_message=(
        "You are a Java code generator. Respond with **one** JSON object ONLY:\n"
        "{ 'files': [ { 'path': '...', 'content': '...' } ] }\n"
        "Return exactly one Java class plus pom.xml. No markdown, no commentary."))

    reviewer = AssistantAgent("Reviewer", llm_config=LLM, system_message=(
        "You are a code reviewer. List up to 5 blocking issues _or_ reply exactly `LGTM`."))

    return [pm, architect, coder, reviewer]

# ---------------------------------------------------------------------------
# 5️⃣ Main runner  ───────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def phase_run(feature: str):
    agents = make_agents()
    user   = UserProxyAgent("User", human_input_mode="NEVER", code_execution_config={"use_docker": False})

    gc  = GroupChat(agents=agents, max_round=12, speaker_selection_method="round_robin", send_introductions=False)
    mgr = GroupChatManager(gc, llm_config=LLM)

    result = user.initiate_chat(
        mgr,
        message=f"We need a new feature: {feature}. Collaborate & output boilerplate code.",
        clear_history=True
    )

    # echo conversation
    print("\n========== CONVERSATION ==========")
    for m in result.chat_history:
        content = str(getattr(m, "content", "")).strip()
        if content:
            print(f"\n[{getattr(m, 'sender', '?')}]\n{content}\n" + "‑"*40)

    msgs = [str(getattr(m, "content", "")) for m in result.chat_history]
    out_dir = write_first_file(msgs)
    print("\nOutput directory:", out_dir.resolve())

# ---------------------------------------------------------------------------
# 6️⃣ Log → markdown exporter  ──────────────────────────────────────────────
# ---------------------------------------------------------------------------

def log_to_md(log_file: Path, md_out: Path):
    hdr = re.compile(r"^\[(.+?)\]$")
    sender, buf, parts = None, [], []

    for line in log_file.read_text("utf‑8", errors="ignore").splitlines():
        m = hdr.match(line.strip())
        if m:
            if sender and buf:
                parts.append((sender, "\n".join(buf).rstrip()))
            sender, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if sender and buf:
        parts.append((sender, "\n".join(buf).rstrip()))

    md_out.write_text("\n\n".join(f"### {s}\n\n{b}\n" for s, b in parts if b.strip()), "utf‑8")
    print(f"[export‑log] wrote {md_out}")

# ---------------------------------------------------------------------------
# 7️⃣ CLI façade  ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap  = argparse.ArgumentParser(description="small Spring‑Boot PoC generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run",        help="run multi‑agent workflow")
    p_run.add_argument("feature",        help="feature description")

    p_msg = sub.add_parser("messages",   help="parse demo_output.md only")
    p_msg.add_argument("markdown", type=Path)

    p_exp = sub.add_parser("export‑log", help="convert run_*.log → demo_output.md")
    p_exp.add_argument("log_file",   type=Path)
    p_exp.add_argument("md_out",     type=Path)

    args = ap.parse_args()

    if args.cmd == "export‑log":
        log_to_md(args.log_file, args.md_out)
        sys.exit()

    if args.cmd == "messages":
        write_first_file([args.markdown.read_text("utf‑8")])
        sys.exit()

    # ensure Ollama reachable
    try:
        import requests; requests.get(OLLAMA_URL.replace("/v1", ""), timeout=2)
    except Exception:
        sys.exit(f"[ERROR] Ollama not reachable at {OLLAMA_URL}. Use export‑log/messages instead.")

    phase_run(args.feature)
