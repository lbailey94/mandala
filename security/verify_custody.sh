#!/usr/bin/env bash
# Read-only custody verifier.
#
# Hashes every active copy in custody_manifest.tsv and compares against the
# registered sha256. Never reads key contents (hashing only) and writes
# nothing. Exit 0 = all active copies verify; exit 1 = drift or missing.
#
#   bash security/verify_custody.sh [manifest.tsv]
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="${1:-$DIR/custody_manifest.tsv}"

if [ ! -f "$MANIFEST" ]; then
  echo "manifest not found: $MANIFEST" >&2
  exit 1
fi

ok=0; drift=0; missing=0; planned=0
while IFS=$'\t' read -r copy_id key_id label uuid path sha status; do
  case "${copy_id:-}" in '' | '#'*) continue ;; esac
  if [ "$status" = "planned" ]; then
    printf 'PLAN  %-4s key %s (not yet created)\n' "$copy_id" "$key_id"
    planned=$((planned + 1))
    continue
  fi
  if [ ! -e "$path" ]; then
    printf 'MISS  %-4s key %s  %s\n' "$copy_id" "$key_id" "$path"
    missing=$((missing + 1))
    continue
  fi
  actual="$(sha256sum "$path" | awk '{print $1}')"
  if [ "$actual" = "$sha" ]; then
    printf 'OK    %-4s key %s  %s\n' "$copy_id" "$key_id" "$path"
    ok=$((ok + 1))
  else
    printf 'DRIFT %-4s key %s\n        expected %s\n        actual   %s\n' \
      "$copy_id" "$key_id" "$sha" "$actual"
    drift=$((drift + 1))
  fi
done < "$MANIFEST"

echo '---'
echo "ok=$ok drift=$drift missing=$missing planned=$planned (cards share label SD_CARD1 — UUID is identity)"
if [ "$drift" -eq 0 ] && [ "$missing" -eq 0 ]; then
  exit 0
fi
exit 1
