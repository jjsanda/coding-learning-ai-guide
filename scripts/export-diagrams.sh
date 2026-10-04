#!/usr/bin/env bash
# Export the Mermaid diagrams embedded in README.md (and docs/) to SVG and PNG
# in docs/images/, for visual review and use outside GitHub.
#
#   Requires: node/npx (mermaid-cli is fetched on demand).
#   Usage: bash scripts/export-diagrams.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/images"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

# Headless Chrome needs --no-sandbox inside containers/CI. If a Chrome is
# already on disk (Puppeteer or Playwright cache), point mermaid-cli at it so
# it doesn't insist on its own pinned build.
PUPPETEER_CFG="$WORK/puppeteer.json"
CHROME="${PUPPETEER_EXECUTABLE_PATH:-$(find "${HOME}/.cache/puppeteer" "${HOME}/.cache/ms-playwright" \
  -type f \( -name chrome-headless-shell -o -name chrome -o -name headless_shell \) 2>/dev/null | head -1)}"
if [ -n "$CHROME" ] && [ -x "$CHROME" ]; then
  printf '{ "executablePath": "%s", "args": ["--no-sandbox", "--disable-setuid-sandbox"] }\n' "$CHROME" > "$PUPPETEER_CFG"
else
  echo '{ "args": ["--no-sandbox", "--disable-setuid-sandbox"] }' > "$PUPPETEER_CFG"
fi

# Extract each ```mermaid block from the given markdown file into WORK/<name>-N.mmd
extract() {
  local file="$1" prefix="$2"
  awk -v out="$WORK" -v prefix="$prefix" '
    /^```mermaid/ { inblk=1; n++; fn=sprintf("%s/%s-%d.mmd", out, prefix, n); next }
    /^```/ && inblk { inblk=0; next }
    inblk { print > fn }
  ' "$file"
}

extract "$ROOT/README.md" readme
for doc in "$ROOT"/docs/*.md; do
  [ -e "$doc" ] || continue
  extract "$doc" "$(basename "${doc%.md}")"
done

shopt -s nullglob
diagrams=("$WORK"/*.mmd)
if [ ${#diagrams[@]} -eq 0 ]; then
  echo "No Mermaid diagrams found."
  exit 0
fi

echo "Exporting ${#diagrams[@]} diagram(s) to $OUT ..."
for mmd in "${diagrams[@]}"; do
  name="$(basename "${mmd%.mmd}")"
  npx -y @mermaid-js/mermaid-cli -p "$PUPPETEER_CFG" -i "$mmd" -o "$OUT/$name.svg" -b transparent
  npx -y @mermaid-js/mermaid-cli -p "$PUPPETEER_CFG" -i "$mmd" -o "$OUT/$name.png" -b white --scale 2
  echo "  ✓ $name.svg / $name.png"
done
echo "Done."
