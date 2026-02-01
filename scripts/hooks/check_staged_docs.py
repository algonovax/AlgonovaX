from __future__ import annotations

import re
import subprocess
import sys
from typing import List, Tuple


def die(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


OPENER = re.compile(
    r"<<-?\s*(?:(['\"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*))"
)


def term_re(tok: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(tok)}\s*$")


def staged_files() -> List[str]:
    # NUL-delimited list of staged files
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"]
    )
    parts = out.split(b"\x00")
    files = [p.decode("utf-8", "replace") for p in parts if p]
    return files


def staged_blob(path: str) -> str:
    try:
        out = subprocess.check_output(["git", "show", f":{path}"])
        return out.decode("utf-8", "replace")
    except Exception:
        return ""


def main() -> int:
    for f in staged_files():
        if not (f.endswith(".md") or f.endswith(".txt")):
            continue

        blob = staged_blob(f)

        # 1) block leaked heredoc marker
        if "> EOF" in blob:
            die(f"staged file contains accidental heredoc marker '> EOF': {f}")

        # 2) parse heredocs: require quoted opener, require terminator exists
        data = blob.splitlines()
        openers: List[Tuple[str, int, bool]] = []  # (tok, line_no, quoted)

        for i, line in enumerate(data, start=1):
            m = OPENER.search(line)
            if not m:
                continue
            q = m.group(1)
            tok = m.group(2) or m.group(3)
            quoted = bool(q)
            openers.append((tok, i, quoted))

        for tok, line_no, quoted in openers:
            if not quoted:
                die(
                    f"unquoted heredoc opener <<{tok} in docs ({f}:{line_no}); use <<'{tok}'"
                )
            tr = term_re(tok)
            if not any(tr.match(x) for x in data[line_no:]):
                die(
                    f"heredoc opener <<'{tok}' at {f}:{line_no} missing terminator line '{tok}'"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
