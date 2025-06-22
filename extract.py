#!/usr/bin/env python
# extract_md_classes.py
"""
Take a conversation Markdown (demo_output.md) and materialise any Java classes
it contains – either literal ```java fences or JSON payloads with "javaClass".
"""

from __future__ import annotations
import json, re, sys
from pathlib import Path

DEST_ROOT = Path("extracted_src")          # where classes are written
DEST_ROOT.mkdir(exist_ok=True)

MD_FENCE = re.compile(
    r"```java\s+(?P<body>.*?)```", re.S | re.I
)
JSON_FENCE = re.compile(
    r"```(?:json)?\s*(?P<json>\{.*?\})\s*```", re.S | re.I
)

def _path_from_package(code: str, cls_name: str) -> Path:
    """If the code has a package line -> com/foo/Bar.java, else default path."""
    m = re.search(r"^\s*package\s+([a-zA-Z0-9_.]+);", code, re.M)
    if m:
        pkg = m.group(1).strip().replace(".", "/")
        return Path(pkg) / f"{cls_name}.java"
    return Path(f"{cls_name}.java")

def write_class(path: Path, code: str):
    dest = DEST_ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(code.rstrip() + "\n", "utf-8")
    print(f"  ✔ wrote {dest}")

def main(md_file: Path):
    text = md_file.read_text(encoding="utf-8")

    # 1) literal ```java``` blocks
    for body in MD_FENCE.findall(text):
        cls_match = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", body)
        if cls_match:
            cls = cls_match.group(1)
            write_class(_path_from_package(body, cls), body)

    # 2) JSON snippets that declare "javaClass"
    for jf in JSON_FENCE.findall(text):
        try:
            data = json.loads(jf)
        except json.JSONDecodeError:
            continue
        jc = data.get("javaClass")
        if not jc:               # might be nested deeper
            continue
        path = jc.get("path") or jc.get("name", "") + ".java"
        code_block = ""          # default stub
        # try to find a code fence immediately after this JSON snippet
        tail = text.split(jf, 1)[1]
        m_code = MD_FENCE.search(tail)
        if m_code:
            code_block = m_code.group("body")
        else:
            # generate a stub if no code present
            cls_name = Path(path).stem
            pkg_line = (
                f"package {Path(path).parent.as_posix().replace('/', '.')};\n\n"
                if '/' in path else ""
            )
            code_block = f"""{pkg_line}public class {cls_name} {{
    public static void main(String[] args) {{
        // TODO: implement
    }}
}}"""
        write_class(Path(path), code_block)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_md_classes.py <demo_output.md>")
        sys.exit(1)
    main(Path(sys.argv[1]))
