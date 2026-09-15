#!/usr/bin/env bash
# Pre-release custody gate (operator-side).
#
# CI cannot see removable media, so this is a local ceremony step, not a CI
# job. Run before tagging a release and record the outcome in the release
# notes.
#
#   bash security/custody_gate.sh
#
# Exit: 0 = all active copies on mounted media verified (release OK);
#       1 = drift or missing on correct media (release BLOCKED);
#       2 = inconclusive (media absent/wrong card) — release allowed only with
#           an explicit disclosure line naming the unverified copies.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$DIR/verify_custody.sh"
rc=$?

case "$rc" in
  0) echo "custody gate: PASS — all mounted copies verified"; exit 0 ;;
  1) echo "custody gate: BLOCKED — drift/missing on correct media; do not tag" >&2; exit 1 ;;
  2) echo "custody gate: INCONCLUSIVE — unverified copies on unmounted/wrong media;"
     echo "  disclose them in the release notes before tagging." ; exit 2 ;;
  *) echo "custody gate: unexpected verifier exit $rc" >&2; exit 1 ;;
esac
