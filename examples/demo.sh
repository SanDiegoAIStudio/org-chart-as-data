#!/bin/sh
# Show the render and check cycle on a throwaway copy of this folder.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/org-chart-demo.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
/bin/cp -f "$root/render.py" "$root/org.json" "$root/ROSTER.md" "$root/OWNERS.md" "$root/README.md" "$tmp/"
cd "$tmp"

fail() {
  printf '%s\n' "$1"
  exit 1
}

need() {
  if printf '%s\n' "$out" | grep -F -q -- "$1"; then
    return 0
  fi
  fail "$2"
}

run_py() {
  set +e
  out=$(python3 "$@" 2>&1)
  code=$?
  set -e
}

printf '%s\n' "(1) render"
run_py render.py
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 1 did not exit 0"; fi
need "unchanged ROSTER.md" "part 1 did not report unchanged ROSTER.md"
need "unchanged OWNERS.md" "part 1 did not report unchanged OWNERS.md"
need "unchanged README.md (block roster)" "part 1 did not report unchanged README.md"
need "rendered 3 outputs from org.json (0 changed)" "part 1 did not report zero changes"

printf '%s\n' "(2) check"
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 2 did not exit 0"; fi
need "views match org.json (3 outputs)" "part 2 did not report a match"

printf '%s\n' "(3) hand edit"
python3 - <<'PY'
from pathlib import Path
path = Path("ROSTER.md")
path.write_text(path.read_text().replace("Ada", "Ava", 1))
PY
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 1 ]; then fail "part 3 did not exit 1"; fi
need "DRIFT: ROSTER.md line" "part 3 did not report drift"
need "  on disk:  " "part 3 did not show the disk line"
need "  expected: " "part 3 did not show the expected line"
need "out of date" "part 3 did not report an out of date view"

printf '%s\n' "(4) render after the hand edit"
run_py render.py
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 4 render did not exit 0"; fi
need "wrote ROSTER.md" "part 4 did not rewrite ROSTER.md"
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 4 check did not exit 0"; fi
need "views match org.json (3 outputs)" "part 4 check did not pass"

printf '%s\n' "(5) block edits"
printf '\nThis sentence sits outside the generated block.\n' >> README.md
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 5 outside edit did not pass"; fi
need "views match org.json (3 outputs)" "part 5 outside edit was treated as drift"
python3 - <<'PY'
from pathlib import Path
path = Path("README.md")
text = path.read_text()
begin = text.index("<!-- org:roster:begin -->")
end = text.index("<!-- org:roster:end -->")
path.write_text(text[:begin] + text[begin:end].replace("Build", "Built", 1) + text[end:])
PY
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 1 ]; then fail "part 5 inside edit did not exit 1"; fi
need "DRIFT: README.md" "part 5 inside edit was not drift"
run_py render.py
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 0 ]; then fail "part 5 render did not exit 0"; fi
need "wrote README.md (block roster)" "part 5 did not restore the block"
if ! grep -F -q "This sentence sits outside the generated block." README.md; then
  fail "part 5 dropped the sentence outside the block"
fi
block_has_built=$(python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text()
begin = text.index("<!-- org:roster:begin -->")
end = text.index("<!-- org:roster:end -->")
print("yes" if "Built" in text[begin:end] else "no")
PY
)
if [ "$block_has_built" != "no" ]; then
  fail "part 5 left the inside edit in place"
fi

printf '%s\n' "(6) shared head"
cksum ROSTER.md OWNERS.md README.md > before.cksum
python3 - <<'PY'
import json
with open("org.json") as handle:
    org = json.load(handle)
for team in org["teams"]:
    if team["name"] == "Sell":
        team["head"] = "Ada"
    if team["name"] == "Run":
        team["members"] = ["Ben"]
with open("org.json", "w") as handle:
    json.dump(org, handle, indent=2)
    handle.write("\n")
PY
run_py render.py
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 1 ]; then fail "part 6 did not exit 1"; fi
need "RULE: " "part 6 did not report a rule"
need "Ada heads both Build and Sell" "part 6 did not name the shared head"
need "nothing was written" "part 6 wrote output after a broken rule"
cksum ROSTER.md OWNERS.md README.md > after.cksum
if ! cmp -s before.cksum after.cksum; then
  fail "part 6 changed an output file"
fi

printf '%s\n' "(7) missing org.json"
mv org.json org.json.away
run_py render.py --check
printf '%s\n' "$out"
printf '%s\n' "exit $code"
if [ "$code" -ne 2 ]; then fail "part 7 did not exit 2"; fi
need "could not check: org.json is missing" "part 7 did not say it could not check"
exit 0
