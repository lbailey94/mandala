# Key Custody Register — WhiteMagic / MandalaOS

**Status:** active (Option 1 adopted 2026-09-14). **This register contains no secret material** — only paths, public fingerprints, media UUIDs, ciphertext hashes, and locations. Never record passphrases or key contents here.

**Scope:** release-signing and identity keys used to sign releases, tags, ledgers, or to authenticate as this machine/node.

## 1. Key inventory

| ID | Key | Path (operational) | At rest | Purpose | Backup status |
|---|---|---|---|---|---|
| **A** | Tag-signing (SSH Ed25519) | `~/.ssh/id_ed25519_signing` (+ `.pub`) | 600, passphrase status unknown | Signs git release tags (`git user.signingkey`, `gpg.format=ssh`); GitHub verifies | **None recorded — action item** |
| **B** | Release-manifest signing (OpenSSH Ed25519) | `~/.config/wm/release-signing.key` | **600, no passphrase** | Local copy of the CI signing key for `release-manifest.json`; `wm update` verifies Ed25519 before install | One GPG-encrypted copy on SD_CARD1 (hash verified `17713cf5…`); second copy unconfirmed |
| **C** | Prescience-ledger signing (Ed25519) | `~/.config/wm/prescience-signing.key` | 600, ASCII | Signs the site prescience ledger (`whitemagic-site/scripts/sign_prescience_ledger.py`) | None recorded — decide (lower stakes; regenerable artifact) |
| **D** | Mesh node identity | `~/.config/wm-mesh-node.key` | 600, 65 B | Sangha mesh identity (not a release key) | None recorded — low stakes; regenerate = new node identity |

Public identities:
- A: `SHA256:cbHGzhbKM5Y73C9fOTzg0BlsjLwu4gi04K6+V1PnPrk` (`lbailey94@protonmail.com (WhiteMagic release signing)`)
- B: fingerprint TBD — record at next decrypt round-trip; public key is pinned by shipped clients (that is what makes B-loss an operational cliff).
- C/D: TBD or non-public.

## 2. Copy inventory

Machine-readable in [`custody_manifest.tsv`](custody_manifest.tsv); verified by [`verify_custody.sh`](verify_custody.sh).

| Copy | Key | Media | UUID | Path | sha256 | Status |
|---|---|---|---|---|---|---|
| C1 | B | `SD_CARD1` | `FA99-F6E6` | `/media/lucas/SD_CARD1/wm-release-signing.key.2026-09-13.gpg` | `17713cf55fd5cd5e326c9dd3ff614c07cbe3a88a1ef6004d9020b4ec1fd9b757` | ✅ active, verified 2026-09-14 |
| A1 | A | `SD_CARD1` | `FA99-F6E6` | `/media/lucas/SD_CARD1/wm-tag-signing.key.2026-09-14.gpg` | `ed040cfdeda2f36bcc604e1a2591c8d48c72a5443109db342953dc86dbf8e0b3` | ✅ active, round-trip verified 2026-09-14 |
| C2 | B | `SD_CARD1` | `FEEC-FCE2` (absent) | unconfirmed | unknown | ⚠ unverified — re-check when card is attached |
| — | C | — | — | — | — | ❌ no copy exists |

**Card identity rule:** three cards share the label `SD_CARD1`; **UUID is the only reliable identity**. Physically label every card `SD_CARD1-<UUID suffix>`.

## 3. Option 1 completion checklist (owner actions)

- [ ] Physically label cards (`SD_CARD1-FA99`, `SD_CARD1-FEEC`, third card TBD)
- [x] **A backup created** — copy A1, 2026-09-14, AES256 / s2k-65011712, round-trip verified byte-identical (`ed040cfd…`)
- [ ] Create a second GPG-encrypted copy of **B** on a *different* card/location → copy B2 *(awaiting the second SD card)*
- [ ] Decide C (back up or accept regeneration); record decision
- [x] **Permissions:** local keys are 600; `~/.gnupg` set to 700 (2026-09-14). *exfat ignores chmod (fmask/dmask=0022) — card copies rely on encryption + physical custody, not Unix perms.*
- [ ] Confirm B backup decrypts and identify its key + fingerprint (A1 already round-trip verified)
- [ ] Verify the GitHub Actions manifest-signing secret matches B; write the rotation runbook (update CI secret + local file + copies)
- [ ] Passphrase paper stored **apart from every copy**; record only its *location* in this register
- [x] Run `security/verify_custody.sh` — 2026-09-14: C1 + A1 OK, B2 planned

## 4. Verification procedure

- **Quarterly (cheap):** `bash security/verify_custody.sh` — hashes each active copy and compares against the manifest. Record the run in the change log.
- **Annually (air-gapped):** decrypt one copy of each key on an offline host, confirm the key works (e.g., `ssh-keygen -lf` / `wm update` dry-run against a fixture), re-encrypt, refresh hashes in the manifest.
- **On any card event** (mount, travel, label change): re-verify; update UUID fields.

## 5. Hardening roadmap (near-future releases)

| Item | Target | Note |
|---|---|---|
| Hardware token for A (FIDO2 `sk-ssh-ed25519`) | next/near-future release | Removes file-at-rest key class; GitHub supports sk key registration |
| Hardware-backed or HSM/CI-only B; retire local unencrypted copy | near-future | Requires rotation runbook + client compatibility note |
| Shamir 2-of-3 paper shares for B across holders/locations | later | Strongest loss+theft story; retire digital copies when mature |
| Custody check added to the release checklist | next release | Fail release if register/verification is stale |

## 6. Change log

| Date | Change |
|---|---|
| 2026-09-14 | Register created (Option 1 adopted). C1 verified: `17713cf5…` matches `CURRENT_REALITY_2026-09-13.md` §8. Card UUID mismatch discovered by parallel lane (see `evidence/RECEIPT_VERIFICATION_ADDENDUM_3_20260914.md`); backup itself intact. A/C/D backups open; B unencrypted-at-rest + no-passphrase noted. |
| 2026-09-14 | **A1 created** on `SD_CARD1` FA99-F6E6 (`wm-tag-signing.key.2026-09-14.gpg`, ciphertext sha256 `ed040cfd…`, key sha256 `80f687e2…` verification-only). Round-trip decrypt byte-identical. `~/.gnupg` chmod 700. exfat chmod limitation recorded. B2 pending the second card. |
