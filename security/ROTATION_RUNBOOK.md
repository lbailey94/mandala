# Key Rotation Runbook — WhiteMagic / MandalaOS

**Scope:** rotating the custody-register keys (see `KEY_CUSTODY_REGISTER.md`). Written 2026-09-14; keep in sync with the register and the release workflow.

**Trigger conditions:** suspected compromise; key loss; scheduled rotation (recommend annual for A and B); role/format change (e.g., moving to a hardware token — roadmap items 2/3).

**Golden rules**
- Never rotate only locally: CI secret, pinned public key, backups, and register must move together.
- Old manifests keep verifying against their recorded pubkey; old tags stay signed by the old key. Rotation changes the *future*, not the past — say so in the release notes.
- After any rotation: refresh backups, update `custody_manifest.tsv`, run `verify_custody.sh`, add a register change-log entry.

## A — tag-signing key (SSH)

1. Generate the new key (passphrase kept per policy):
   `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_signing_new -C "lbailey94@protonmail.com (WhiteMagic release signing)"`
2. Register the public key with GitHub as a signing key:
   `gh ssh-key add ~/.ssh/id_ed25519_signing_new.pub --type signing`
3. Update `~/.config/git/allowed_signers` (the second line must carry the new public key).
4. Point git at the new key if the path changed: `git config --global user.signingkey ~/.ssh/id_ed25519_signing_new.pub`
5. Prove it: sign a throwaway annotated tag in a scratch clone, push it, confirm GitHub shows **Verified**; then delete the test tag.
6. Back up via `bash security/make_backup.sh ~/.ssh/id_ed25519_signing_new /media/lucas/<card>/wm-tag-signing.key.<date>.gpg`; register as A2; retire A1 after a grace period (keep one historical copy until the next successful release cycle).
7. Remove the old public key from GitHub **only after** the new one verifies.

## B — release-manifest key (Ed25519)

1. Generate a new Ed25519 key in PKCS#8 form; derive the PEM (what CI consumes) and the raw public hex (what verifiers pin).
2. Replace the local file `~/.config/wm/release-signing.key` in the same format (comment lines + base64 PKCS#8 line) so the custody tooling and backups keep working.
3. Set the CI secret (PEM):
   `gh secret set RELEASE_SIGNING_KEY -R lbailey94/whitemagic < new-key.pem`
4. Set the pinned public key:
   `gh variable set WM_RELEASE_PUBKEY -R lbailey94/whitemagic --body "<raw-hex-pubkey>"`
5. Reconcile references to the pin (`release_manifest.rs` doc comment mentions `scripts/install.sh`; keep source-of-truth wording consistent).
6. Cut a release and verify end-to-end: download `release-manifest.json` + `.sig`, verify against the new pubkey, then `wm update` on a scratch install.
7. Back up both the new seed and (if the format changed) the PEM recipe; refresh C/B copies; register hashes; note the lineage era in the release notes.
8. Removal gate: do not revoke/rotate the old key until one release signs, distributes, and updates successfully with the new one.

## C — prescience-ledger key

1. Rotate = generate a new ASCII Ed25519 key at `~/.config/wm/prescience-signing.key`; the site re-signs the ledger on its next publish.
2. Old signatures remain valid against the old public key — publish the new public key alongside the ledger.
3. Back it up on the next card session if the decision is to keep it (still pending).

## D — mesh node identity

- Separate material from B (shares only the format convention). Rotation creates a **new node identity** and affects record-attestation lineage; coordinate with the S9 lineage notes before rotating. No release dependency.

## Cosign

- Artifacts use **keyless Sigstore signing** — nothing to rotate; the transparency-log identity is the trust anchor.

## Post-rotation checklist (copy into the release notes)

- [ ] New key registered at its consumer (GitHub / CI secret / variable / config)
- [ ] One end-to-end proof passed (verified tag or verified manifest + `wm update`)
- [ ] New backup created via `make_backup.sh`, hash registered, `verify_custody.sh` green for mounted media
- [ ] Register updated (key inventory, copies, change log)
- [ ] Old material retired per its removal gate
