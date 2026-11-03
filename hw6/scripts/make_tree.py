"""Problem 10: write the repo's file tree into README.md (between the tree markers).

Lists exactly the files git would commit (no .env, no .venv), in the same style
as the assignment's expected repo, with the document folders collapsed.

Run from the project folder:  .venv/Scripts/python scripts/make_tree.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
START, END = "<!-- tree:start -->", "<!-- tree:end -->"
COLLAPSE = {"data/practice_docs": "(the 12 practice documents)", "data/exam_docs": "(the 10 exam documents)",
            "data/my_attacks": "(our two attack files + their answer key)",
            "output/person_view": "(screenshots: documents as a person sees them)",
            "output/reports": "(the latest report for each document)"}
TOP = ["AI_prompts.md", "README.md", ".gitignore", ".env.example", "requirements.txt", "agent.py", "tools.py",
       "models.py", "EVIDENCE_CHECKLIST.md", "prompts/", "data/", "output/", "scripts/"]


def committed() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return sorted(Path(line) for line in out.splitlines() if line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        skip = {".venv", "__pycache__", ".git"}
        return sorted(p.relative_to(ROOT) for p in ROOT.rglob("*")
                      if p.is_file() and not skip & set(p.relative_to(ROOT).parts) and p.name != ".env")


def build() -> str:
    tree: dict = {}
    for f in committed():
        parts = f.parts
        if "/".join(parts[:2]) in COLLAPSE:
            parts = (parts[0], parts[1] + "/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node.setdefault(parts[-1], None)

    def order(name: str):
        return (TOP.index(name) if name in TOP else 50, name.lower())

    lines = ["hw6/"]

    def walk(node: dict, prefix: str, path: str) -> None:
        names = sorted(node, key=order)
        for i, name in enumerate(names):
            last = i == len(names) - 1
            note = COLLAPSE.get((path + name).rstrip("/"), "")
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}{'   ' + note if note else ''}")
            if isinstance(node[name], dict):
                walk(node[name], prefix + ("    " if last else "│   "), path + name)

    walk(tree, "", "")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    tree = build()
    text = README.read_text(encoding="utf-8")
    if START in text and END in text:
        head, rest = text.split(START, 1)
        README.write_text(f"{head}{START}\n```\n{tree}\n```\n{END}{rest.split(END, 1)[1]}", encoding="utf-8")
        print("README.md tree updated")
    print(tree)
