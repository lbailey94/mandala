# Key Custody Register — WhiteMagic / MandalaOS

**Status:** active (Option 1 adopted 2026-09-14). **This register contains no secret material** — only paths, public keys/fingerprints, media UUIDs, ciphertext hashes, and locations. Never record passphrases or key contents here.

**Scope:** release-signing and identity keys used to sign releases, tags, ledgers, or to authenticate as this machine/node.

## 1. Key inventory

| ID | Key | Path (operational) | Format / at rest | Purpose | Backup status |
|---|---|---|---|---|---|
| **A** | Tag-signing key | `~/.ssh/id_ed25519_signing` (+ `.pub`) | OpenSSH Ed25519, 600 | Signs git release tags (`git user.signingkey`, `gpg.format=ssh`); public key is line 2 of `~/.config/git/allowed_signers`; GitHub verifies | **A1** ✅ on SD_CARD1 `FA99-F6E6` (round-trip verified) |
| **B** | Release-manifest signing key | `~/.config/wm/release-signing.key` | **base64(PKCS#8 DER Ed25519, 48 B) + 2 comment lines**; 600; **no passphrase** | Signs `release-manifest.json`; CI uses `secrets.RELEASE_SIGNING_KEY` (PEM) + `openssl pkeyutl`; public key pinned as repo variable `WM_RELEASE_PUBKEY` | **C1 + B2** ✅ (both round-trip verified) |
| **C** | Prescience-ledger signing key | `~/.config/wm/prescience-signing.key` | ASCII Ed25519 (91 B), 600 | Signs the site prescience ledger (`whitemagic-site/scripts/sign_prescience_ledger.py`) | ❌ none — **decision pending** |
| **D** | Mesh node identity | `~/.config/wm-mesh-node.key` | 64-char hex seed, 600 | Sangha mesh identity + record-attestation lineage (separate material from B; same *format convention*) | ❌ none — medium stakes |

**Public identities (recorded for verification):**

| Key | Public identity |
|---|---|
| A | `SHA256:cbHGzhbKM5Y73C9fOTzg0BlsjLwu4gi04K6+V1PnPrk` (`lbailey94@protonmail.com (WhiteMagic release signing)`) |
| B | Ed25519 pubkey `aade884b035d2f92333843faba153eb83b201d1d1db63e25d642d82f4b12770e` (= repo variable `WM_RELEASE_PUBKEY`) |
| D | Ed25519 pubkey `8e2595399e75849f3b6e3988e17becb94f8f9c74730c8a454302cf851e767127` |
| C | TBD (not derived; do at next round-trip) |

**Identity chain proven 2026-09-14:** B's seed → derived pubkey `aade884b…` → **verifies the shipped v9.1.5 `release-manifest.json` signature** (`openssl pkeyutl -verify` → *Signature Verified Successfully*). CI secret `RELEASE_SIGNING_KEY` exists (updated 2026-09-13T22:51:26Z), same minute as the `WM_RELEASE_PUBKEY` variable.

## 2. Copy inventory

Machine-readable in [`custody_manifest.tsv`](custody_manifest.tsv); verified by [`verify_custody.sh`](verify_custody.sh).

| Copy | Key | Media | UUID | Path | Ciphertext sha256 | Status |
|---|---|---|---|---|---|---|
| C1 | B | `SD_CARD1` | `FA99-F6E6` | `.../wm-release-signing.key.2026-09-13.gpg` | `17713cf55fd5cd5e326c9dd3ff614c07cbe3a88a1ef6004d9020b4ec1fd9b757` | ✅ verified (off-machine now) |
| A1 | A | `SD_CARD1` | `FA99-F6E6` | `.../wm-tag-signing.key.2026-09-14.gpg` | `ed040cfdeda2f36bcc604e1a2591c8d48c72a5443109db342953dc86dbf8e0b3` | ✅ round-trip verified (off-machine now) |
| B2 | B | `SD_CARD1` | `FEEC-FCE2` | `.../wm-release-signing.key.2026-09-14.gpg` | `d455b81cddc5c0c7db3917dd3d8009fca2dac29b0ee40561deafe4b8f17e5470` | ✅ round-trip verified |
| C2 candidate | B | `SD_CARD1` | `FEEC-FCE2` (archives card) | — | — | ⚠ not checked (receipted archives only) |

**Card identity rule:** three cards share the label `SD_CARD1`; **UUID is the only reliable identity**. Physically label every card `SD_CARD1-<UUID suffix>` (pending).

## 3. Option 1 completion checklist

- [ ] Physically label cards (`SD_CARD1-FA99`, `SD_CARD1-FEEC`, third card TBD)
- [x] **A backup** — A1, 2026-09-14, AES256 / s2k-65011712, round-trip byte-identical
- [x] **Second B copy** — B2, 2026-09-14, round-trip byte-identical; derived pubkey + signature chain verified
- [ ] Decide C: back it up (cheap, uniform practice) or accept regeneration — recommendation: back up on the next card session
- [x] **Permissions:** local keys 600; `~/.gnupg` 700. *exfat ignores chmod (fmask/dmask=0022) — card copies rely on encryption + physical custody, not Unix perms.*
- [x] **B identity + round-trip** resolved (see §1 identity chain); C1 re-check when `FA99-F6E6` returns (expected: same key hash `78dcca87…`)
- [x] **CI secret check:** `RELEASE_SIGNING_KEY` present; `WM_RELEASE_PUBKEY` matches B's derived pubkey. *(Note: `release_manifest.rs` doc comment says the pubkey is pinned in `install.sh`, but no literal pin was found there — reconcile wording during rotation runbook maintenance.)*
- [ ] Passphrase paper stored apart from every copy; register records only its location (owner statement)
- [x] `verify_custody.sh` baseline: C1 + A1 + B2 all verified across two cards

## 4. Verification procedure

- **Quarterly:** `bash security/verify_custody.sh` — hashes each mounted active copy. Absent media reports `ABSENT` and exits 2 (inconclusive), never a silent pass.
- **Annually (air-gapped):** decrypt one copy of each key, then:
  - A: `ssh-keygen -lf` of the decrypted key;
  - B: derive pubkey (base64 → PKCS#8 → raw pub) and verify a downloaded release manifest signature with it;
  - re-encrypt/refresh hashes.
- **On any card event** (mount, travel, label change): re-verify; update UUID fields.

## 5. Hardening roadmap (near-future releases)

| Item | Target | Note |
|---|---|---|
| Hardware token for A (FIDO2 `sk-ssh-ed25519`) | next/near-future release | Removes file-at-rest key class; GitHub supports sk key registration |
| B: retire the unencrypted local seed copy; move signing to token/HSM or CI-only with a documented recovery path | near-future | Requires rotation runbook + client compatibility note |
| Shamir 2-of-3 paper shares for B across holders/locations | later | Strongest loss+theft story |
| Custody check added to the release checklist | next release | Fail release if register/verification is stale |

## 6. Change log

| Date | Change |
|---|---|
| 2026-09-14 | Register created (Option 1 adopted). C1 verified `17713cf5…`; card UUID mismatch from the parallel lane's addendum 3 explained (wrong card mounted); backup intact. |
| 2026-09-14 | **A1 created** (AES256/s2k-65011712, `ed040cfd…`; round-trip byte-identical). `~/.gnupg` → 700; exfat chmod limitation recorded. |
| 2026-09-14 | **B2 created on `FEEC-FCE2`** (`d455b81c…`; round-trip byte-identical). **B identified:** base64 PKCS#8 seed; derived pubkey `aade884b…` = `WM_RELEASE_PUBKEY`; **signature chain verified** against v9.1.5 manifest. D confirmed as a separate key (`8e259539…`). Receipted archives re-verified on `FEEC-FCE2` (tar sidecar OK; mdb `c4ef73e8…`). |
