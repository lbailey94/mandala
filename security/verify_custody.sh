#!/usr/bin/env bash
# Read-only custody verifier.
#
# For every active copy in custody_manifest.tsv:
#   1. resolve the UUID of the filesystem actually mounted at the copy's path
#      (UUID is the only identity — three cards share the label SD_CARD1 and
#      they all mount at /media/lucas/SD_CARD1);
#   2. if it differs from the registered UUID → WRONG-MEDIA (inconclusive,
#      the card is off-machine or swapped);
#   3. if it matches but the file is gone → MISSING (a real finding);
#   4. otherwise hash the ciphertext and compare to the registered sha256.
#
# Exit: 0 = all active copies on mounted media verified;
#       1 = drift or missing on the correct media;
#       2 = inconclusive (some media absent/wrong).
#
#   bash security/verify_custody.sh [manifest.tsv]
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="${1:-$DIR/custody_manifest.tsv}"

if [ ! -f "$MANIFEST" ]; then
  echo "manifest not found: $MANIFEST" >&2
  exit 1
fi

ok=0; drift=0; missing=0; absent=0; wrong=0; planned=0
while IFS=$'\t' read -r copy_id key_id label uuid path sha status; do
  case "${copy_id:-}" in '' | '#'*) continue ;; esac
  if [ "$status" = "planned" ]; then
    printf 'PLAN  %-4s key %s (not yet created)\n' "$copy_id" "$key_id"
    planned=$((planned + 1))
    continue
  fi

  mount_uuid="$(findmnt -no UUID -T "$(dirname "$path")" 2>/dev/null || true)"
  if [ -z "$mount_uuid" ]; then
    printf 'ABSENT %-4s key %s  (no media mounted at %s)\n' "$copy_id" "$key_id" "$(dirname "$path")"
    absent=$((absent + 1))
    continue
  fi
  if [ "$mount_uuid" != "$uuid" ]; then
    printf 'WRONG-MEDIA %-4s key %s\n        want card %s, mounted card is %s\n' \
      "$copy_id" "$key_id" "$uuid" "$mount_uuid"
    wrong=$((wrong + 1))
    continue
  fi
  if [ ! -e "$path" ]; then
    printf 'MISSING %-4s key %s  %s  (card %s mounted, file gone)\n' "$copy_id" "$key_id" "$path" "$uuid"
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
echo "ok=$ok drift=$drift missing=$missing wrong_media=$wrong absent=$absent planned=$planned"
echo '(three cards share label SD_CARD1; mountpoint /media/lucas/SD_CARD1 is identical across them — UUID anchoring is what this script checks)'

if [ "$drift" -gt 0 ] || [ "$missing" -gt 0 ]; then
  exit 1
fi
if [ "$wrong" -gt 0 ] || [ "$absent" -gt 0 ]; then
  exit 2
fi
exit 0
