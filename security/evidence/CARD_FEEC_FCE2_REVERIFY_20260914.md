# Card re-verification — FEEC-FCE2 mount + B2 creation (2026-09-14)

Read-only verification with the receipted card mounted; B2 backup written
(Model A, owner present). No secret material below.

## Addendum-3 resolution

The `FEEC-FCE2` card (59.5 GB, exfat) was inserted and mounted at
`/media/lucas/SD_CARD1` (20:07 EDT). The files the parallel lane's addendum
could not find are present:

| File | Size | Check |
|---|---|---|
| `whitemagic-archives/v26-heritage-20260911.tar.zst` | 320,440,015 B | **sidecar `sha256sum -c` → OK** |
| `whitemagic-archives/vault-data-pre-redactstore-20260911.mdb` | 2,542,604,288 B | sha256 `c4ef73e8ccde925ae3d5bfd7f69d824e92d31d6fa3ee9b335b20aa595d599bce` (recorded; no sidecar) |

**Verdict:** the earlier "files absent" finding was a wrong-card mount, exactly
as addendum 3 diagnosed. The overlap analysis itself (per-DBI key sets) still
needs the pinned `python-lmdb` environment to be reproducible; that remains
open as a method gap, not a data gap.

## B2 creation and identity chain

- Backup written: `wm-release-signing.key.2026-09-14.gpg` at the card root
  (AES256, s2k mode 3, count 65,011,712).
- Ciphertext sha256 `d455b81cddc5c0c7db3917dd3d8009fca2dac29b0ee40561deafe4b8f17e5470`.
- Round-trip: decrypted output byte-identical to `~/.config/wm/release-signing.key`
  (key hash `78dcca87…`, matching the value recorded in `CURRENT_REALITY` §8).
- The local key is base64(PKCS#8 DER Ed25519) with comment lines (48-byte DER).
- Derived public key: `aade884b035d2f92333843faba153eb83b201d1d1db63e25d642d82f4b12770e`
  = repo variable `WM_RELEASE_PUBKEY`.
- **Signature chain:** derived pubkey verifies the shipped v9.1.5
  `release-manifest.json` signature (`openssl pkeyutl -verify` →
  *Signature Verified Successfully*).
- Mesh node key is a **separate** key (derived pubkey `8e259539…`), sharing the
  format convention only.

## Reproduce (public material only)

```bash
sed -n '2p' ~/.config/wm/release-signing.key | base64 -d \
  | openssl pkey -inform DER -pubout -outform DER | tail -c 32 | xxd -p -c 64
# → aade884b035d2f92333843faba153eb83b201d1d1db63e25d642d82f4b12770e
```
