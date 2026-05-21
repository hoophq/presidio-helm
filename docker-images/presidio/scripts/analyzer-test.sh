#!/usr/bin/env bash
#
# Send text to a running Presidio analyzer and pretty-print the findings.
#
# Examples:
#   analyzer-test.sh my cpf is 111.444.777-35
#   echo "my cpf is 111.444.777-35" | analyzer-test.sh
#   analyzer-test.sh <<EOF
#   line one mentions 111.444.777-35
#   line two has an email foo@bar.com
#   EOF
#
# Environment overrides:
#   ANALYZER_URL      default: http://localhost:3000
#   LANGUAGE          default: en
#   SCORE_THRESHOLD   default: 0          (analyzer-side filter, 0..1)
#   ENTITIES          default: (all)      comma-separated, e.g. BR_CPF,EMAIL_ADDRESS

set -euo pipefail

if [ "$#" -gt 0 ]; then
    text="$*"
elif [ ! -t 0 ]; then
    text="$(cat)"
else
    sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 1
fi

# Reject input that's only whitespace.
if [ -z "${text//[[:space:]]/}" ]; then
    echo "error: empty input" >&2
    exit 1
fi

# Hand the text to Python via argv to sidestep all shell quoting.
exec python3 - "$text" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

text             = sys.argv[1]
url              = os.environ.get("ANALYZER_URL", "http://localhost:3000").rstrip("/")
language         = os.environ.get("LANGUAGE", "en")
score_threshold  = float(os.environ.get("SCORE_THRESHOLD", "0") or 0)
entities_env     = os.environ.get("ENTITIES", "").strip()


def c(s: str, color: str) -> str:
    """ANSI-colorize when stdout is a tty, otherwise pass through."""
    if not sys.stdout.isatty():
        return s
    codes = {
        "red": "31", "green": "32", "yellow": "33",
        "cyan": "36", "dim": "2", "bold": "1",
    }
    return f"\x1b[{codes[color]}m{s}\x1b[0m"


body = {
    "text": text,
    "language": language,
    "score_threshold": score_threshold,
}
if entities_env:
    body["entities"] = [e.strip() for e in entities_env.split(",") if e.strip()]

req = urllib.request.Request(
    url + "/analyze",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        results = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    sys.stderr.write(f"HTTP {e.code} from {url}/analyze\n")
    sys.stderr.write(e.read().decode("utf-8", errors="replace") + "\n")
    sys.exit(2)
except urllib.error.URLError as e:
    sys.stderr.write(f"cannot reach {url}: {e.reason}\n")
    sys.exit(3)

# --- INPUT ----------------------------------------------------------------
print(c("INPUT", "bold"))
for line in text.splitlines() or [""]:
    print(f"  {line}")
print()

# --- FINDINGS -------------------------------------------------------------
print(c(f"FINDINGS ({len(results)})", "bold"))
if not results:
    print(c("  (no entities detected)", "dim"))
else:
    results_sorted = sorted(results, key=lambda r: (r.get("start", 0), r.get("end", 0)))
    width = max(len(r.get("entity_type", "")) for r in results_sorted)
    for r in results_sorted:
        et    = r.get("entity_type", "?")
        start = r.get("start")
        end   = r.get("end")
        score = r.get("score", 0.0)
        match = text[start:end] if start is not None and end is not None else ""
        print(
            f"  {c(et.ljust(width), 'cyan')}  "
            f"score={score:.2f}  "
            f"span=[{start}..{end}]  "
            f"{c(repr(match), 'yellow')}"
        )

# --- ANNOTATED ------------------------------------------------------------
if results:
    print()
    print(c("ANNOTATED", "bold"))
    spans = sorted(
        ((r["start"], r["end"], r["entity_type"]) for r in results
         if r.get("start") is not None and r.get("end") is not None),
        key=lambda s: (s[0], -s[1]),  # outer spans first so overlaps prefer the wider
    )
    out, cursor = [], 0
    for start, end, et in spans:
        if start < cursor:
            # Drop matches overlapping a previously rendered span to keep the
            # output readable. The findings list above still shows them all.
            continue
        out.append(text[cursor:start])
        out.append(c(f"<{et}>", "green"))
        out.append(c(text[start:end], "red"))
        out.append(c(f"</{et}>", "green"))
        cursor = end
    out.append(text[cursor:])
    for line in "".join(out).splitlines():
        print(f"  {line}")
PY
