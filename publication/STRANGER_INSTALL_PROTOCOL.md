# Stranger-install protocol — publication Gate-2 (draft, 2026-09-15)

**Gate:** ≥ 4/5 testers install the published artifact **unassisted**, with no
data loss, no silent corruption, and no undisclosed network transfer
(ADOPTION_IMPLICATIONS §5, item 3; CURRENT_REALITY §7).

**Artifact under test (current build-now form):** the public
`mandalaos-sovereign` repo at a frozen commit — clone → build the VM → boot →
run the containment matrix → start WM in-guest → dashboard. WM itself
(`lbailey94/whitemagic`, v9.1.6) is exercised via the Nix-built `wm` binary
inside the VM closure.

---

## 1. Tester profile and environment

- Not the author; has not seen the repo before this test.
- Comfortable with Linux basics (shell, SSH); **no Nix or WhiteMagic
  background required** — that is what the test measures.
- Machine: x86_64, ≥ 16 GB RAM, ≥ 20 GB free disk, Linux with KVM, network
  access. (The full rebuild from a cold Nix store is ~1.7 GiB download /
  ~6.6 GiB unpacked; with a warm store it is minutes.)

## 2. Preconditions for a valid test

1. Docs and repo are frozen: record the commit SHA and doc hashes before the
   tester starts.
2. No live help from the author. Every question is **logged, not answered**
   (answers given are doc bugs — they feed the fix list).
3. Tester uses a scratch home or VM; the point is to prove *their* machine is
   untouched outside the declared directories.

## 3. Procedure (what the tester is given)

The tester receives only: repo URL + "follow `GETTING_STARTED.md`". Expected
path:

```bash
git clone <repo> && cd mandalaos-sovereign
# read GETTING_STARTED.md, then:
nix build .#nixosConfigurations.mandala-vm.config.system.build.vm
./result/bin/run-mandala-node-vm         # boots the VM (QEMU/KVM)
# in-guest:
/etc/mandala/verify-sandbox.sh           # containment matrix
wm --version && wm doctor                # daemon + governance checks
# host:
python3 <LAKSHMI>/lakshmi.py --once      # harmony vector (if LAKSHMI is part of the frozen artifact)
```

Time-box: 2 hours to a booted VM + green matrix. Record wall-clock time to
each milestone.

## 4. What we record per tester (`stranger_<tester>.md`)

- Environment (distro, kernel, RAM/disk, Nix install state).
- Timeline: clone → build start → build end → first boot → matrix green.
- Every question asked, verbatim, with the doc location that failed to answer
  it (or "no doc covers this").
- Every error text, verbatim, and the recovery the tester found (or didn't).
- Network observations (see §6).
- Post-run filesystem diff of the scratch home (see §5).
- Verdict: pass/fail + which criterion failed.

## 5. Data-loss and silent-corruption checks

Before/after (on the tester's machine):

```bash
# seed: checksum a sample of the tester's home + a scratch project dir
find ~/scratch -type f -exec sha256sum {} + > before.sha256
# after the test:
sha256sum -c before.sha256
```

- No writes outside: the repo dir, `~/.cache/nix`/`/nix`, `~/.local/share/lakshmi*`,
  `~/.local/share/yama-collector`, and the repo's declared state dirs.
  (`find ~ -newer before.stamp -not -path '<allowed>*'` as evidence.)
- Corruption: `wm selftest` (host and in-guest) returns green; in-guest
  `wm doctor` reports the store healthy; re-running the matrix is idempotent.

## 6. Network-transfer disclosure

Disclose up front (in `GETTING_STARTED`): the build fetches from
`cache.nixos.org` and the flake inputs from `github.com`; npm launcher (if the
tester uses it) fetches from `registry.npmjs.org`. Everything else must be
explained.

Checks:

```bash
# while idle after boot, sample connections for 60 s (host + guest)
ss -tunp | grep -v '<expected endpoints>'
```

Any connection to an endpoint not on the disclosed list = **critical
failure**; stop, preserve `ss`/journal output, and do not continue.

## 7. Acceptance

- **Pass:** ≥ 4/5 testers reach a booted VM with the matrix green within the
  time-box, zero data loss, zero silent corruption, zero undisclosed transfers.
- Critical failures (data loss, undisclosed transfer) halt the run
  immediately; the affected install does not count toward the 5.
- Failures are doc bugs until proven otherwise: each one becomes a fix list
  item with the tester's verbatim report.

## 8. Dry-run gaps already found (2026-09-15, must fix before inviting testers)

1. `MANDALAOS_SOVEREIGN/GETTING_STARTED.md` still references the pre-move paths
   (`~/Desktop/projects/MANDALAOS_SOVEREIGN/`, `~/Desktop/projects/LAKSHMI/`);
   the repositories live under `~/Desktop/MANDALA_OS/`.
2. Its status header says "matrix 8/8" — actual is 13/13 (2026-09-14 rebuild,
   kernel 6.18 guest / 7.0 host).
3. The S4 runbook (now corrected) shows the level of install friction a
   stranger would hit: NixOS has no `/usr/lib/systemd/system`, the Tetragon
   bundle's `install.sh` aborts there, and `tetra` needs a pty. None of this
   belongs in the stranger path — the VM must ship these ready or the test
   measures the wrong thing.
4. Pin the exact commits in `GETTING_STARTED` so "frozen artifact" is
   checkable; today the doc is date-stamped but not SHA-stamped.

## 9. Evidence location

`publication/evidence_<YYYY-MM-DD>/stranger_<tester>.md` per tester, plus
`gate2_summary.md` with the 5 verdicts and the fix list. Commit with the gate
decision; update `CURRENT_REALITY` §7 at the same time.
