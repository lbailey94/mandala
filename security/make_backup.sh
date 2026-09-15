#!/usr/bin/env bash
# Canonical key-backup helper (custody register, Option 1).
#
#   bash security/make_backup.sh <key-file> <output.gpg>
#
# Encrypts one private key with GPG symmetric AES-256 (s2k mode 3, maximum
# iteration count) via the desktop pinentry prompt. The passphrase is typed
# into the GPG dialog and never passes through a shell, file, or agent
# session. Refuses to overwrite. Verifies the result is an encrypted OpenPGP
# blob and prints its sha256 for registration in custody_manifest.tsv.
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $0 <key-file> <output.gpg>" >&2
  exit 2
fi

KEY="$1"
OUT="$2"

[ -f "$KEY" ] || { echo "key not found: $KEY" >&2; exit 2; }
[ -e "$OUT" ] && { echo "refusing to overwrite: $OUT" >&2; exit 2; }

# Notes for the operator:
# - The GPG dialog asks for the passphrase twice (enter + confirm).
# - Use the existing paper passphrase, or a new one you write down immediately.
# - Never paste the passphrase into a chat, shell history, or script.
gpg --symmetric --cipher-algo AES256 --s2k-mode 3 --s2k-count 65011712 \
    --output "$OUT" "$KEY"

echo "--- packet inspection (metadata only) ---"
gpg --list-packets "$OUT" 2>/dev/null | sed -n '1,3p' || true

if gpg --list-packets "$OUT" 2>/dev/null | grep -q 'symkey enc packet'; then
  echo "confirmed: symmetric OpenPGP encryption"
else
  echo "WARNING: could not confirm encryption — inspect before trusting it" >&2
  exit 1
fi

echo "--- checksum ---"
sha256sum "$OUT"
echo
echo "Next: add this hash to security/custody_manifest.tsv, then run:"
echo "  bash security/verify_custody.sh"
echo "Reminder: paper passphrase stays apart from every copy."
