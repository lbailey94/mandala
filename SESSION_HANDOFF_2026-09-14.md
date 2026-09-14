# Session Handoff — 2026-09-14 (website truth pass pickup)

**Read first:** `SESSION_HANDOFF_2026-09-13.md` §12–18 (the software session:
telemetry retention, release health, `wm setup`, 9.1.5 prep, landrun runner,
threat model). This doc covers the website workstream and where to pick up.

---

## 0. State of the world (end of 2026-09-14 early UTC)

| Repo | Branch | Head | Notes |
|---|---|---|---|
| `whitemagic` (WMv9) | `main` | `95be6dc` | manifest commit local — push held (main sits behind the concurrent session's 7 unpushed commits); `f62c790`/`c08b982` already pushed |
| `whitemagic-site` | `master` | `bda815d` | pushed to production and live-verified; deploy = push on this repo |
| `mandalaos-sovereign` | `main` | `aa80550` | pushed; VM unit points at `v5kjrw43…-nixos-vm` (13/13 matrix green in-guest) |
| `lakshmi` | `main` | `a6cabb7` | clean, pushed |

**Software queue (unchanged):** release-eng item 3 (first live `wm update` at
9.1.5) needs the tag; prep is parked per Lucas (`f62c790`, `c08b982` — version
truth tool, changelog draft, dry-run green). Publication gates left: stranger
install, repo hygiene, edge-galaxy 72 h (fires ~Sep 16 23:36Z).

---

## 1. Website review — verdict and what it means

Lucas's review: the new homepage structure is right (clear hero → install CTA →
MCP compatibility → three proof points → continuity example → CTA). **No big
redesign.** The work is a **truth-and-consistency pass**:

1. Generate every version/stat/platform fact from one authority.
2. Reconcile contradictions, tense, and platform claims.
3. Calibrate over-strong claims (98%, NLU, firsts, "emergent care").
4. Clean Enterprise legal/licensing language.
5. Push the R&D sprawl into a lab-portfolio structure with linked project
   identities.
6. Freeze the homepage structure and measure install/activation.

Note: a parallel session already fixed some items *after* the review was
written — verify current state before editing:

| Review item | Current local state |
|---|---|
| Homepage says v9.1.2 / released Sep 12 | **Fixed locally**: `lib/facts.ts` version `9.1.4`; `lib/i18n.ts` `installReceipts` renders `{version}` + "released Sep 13, 2026" (date still hardcoded — see §2) |
| "cuts token costs by 98%" | **Fixed locally**: `heroTagline` now "measured up to 98% less tool/context overhead in our workloads" |
| GDPR/HIPAA categorical claim | **Fixed locally**: enterprise line 37 now "can create GDPR, HIPAA, confidentiality, data-residency, and corporate-governance obligations" |
| Architecture v9.1.2 install walkthrough | No `9.1.2` strings remain in live files (only `staged/` history) — confirm against the deployed build |
| Dream 12-phase vs 8-phase | Live tree says **12** (`wm-cognitive/src/dream.rs`, architecture lines 84/123). 8-phase exists only in `.bak`/history. Reconcile any live 8-phase leftovers and fix deployment |
| "Enterprise Sovereign License" | No occurrence found in live files — likely already renamed; re-check the deployed page |

---

## 2. The authority chain (ranked above everything else)

**Goal:** `release-manifest.json` is the single authority for version, release
date, platforms, binary size, crate count, test count, benchmark snapshot, and
supported profile — website + README + llms.txt + package metadata consume it.
No manually typed versions anywhere.

Current pipeline is stale: `scripts/sync_facts.py` targets a retired Python
tree (`~/Desktop/WHITEMAGIC/core`, pytest) that no longer exists; `facts.ts`
is hand-maintained. That is the drift source.

### WMv9 side (extend the canonical artifact)

`scripts/release_manifest.py` currently emits `schema/channel/version/
published/minimum_store_schema/targets{url,sha256,signature}`. Extend it
(additive; `update.rs`'s `ReleaseManifest` has `#[serde(default)]` fields and
no deny-unknown-fields, so old clients keep working):

- per-target `size` (bytes) and `install_gated` (bool; true only for
  `linux-x86_64` today, per README §Install path)
- `crates` (workspace publishable count — reuse `crates_publish_order.py`)
- `tests` `{passed, ignored, failed, source}` from the CI run / a
  `--tests-json` input
- `benchmarks` (optional; parse `benchmark_results.txt` when supplied)
- `supported_profile` (e.g. `curated` default, full-profile counts)
- keep `schema: 1` (additive), bump only on breaking changes

### Site side (replace the legacy sync)

New `scripts/sync_release_facts.py`:

- input: `--manifest <url|path>` defaulting to the signed
  `releases/latest/download/release-manifest.json`
- verifies/ships the manifest snapshot to `public/api/release-manifest.json`
  (one checked-in artifact the build reads offline)
- emits `lib/generated/release.json`: version, tag, published date, channel,
  targets (incl. size/gated), crates, tests, benchmarks, supported platforms
- `lib/facts.ts` imports the generated JSON for all release-derived fields
  (version, `verifiedDate`, `crates`, tests, perf/benchmark when present);
  qualitative copy stays hand-written
- `lib/i18n.ts` `installReceipts` gets `{date}` from the generated facts
  instead of the hardcoded "released Sep 13, 2026"
- `app/api/manifest/route.ts` + `public/api/manifest.json` render from the
  same generated source
- `package.json`: `sync-facts` → new script; `check-facts` → verifies the
  generated JSON matches the checked-in manifest (offline-safe) and fails CI
  on drift
- README/llms.txt: WMv9 consumes the same manifest fields for its typed
  header where it prints versions (documented follow-up in the WMv9 repo)

**Acceptance:** changing only `release-manifest.json` (fixture) changes every
rendered version/date/platform/size on the site; `npm run check-facts` fails
on any drift; no `9.1.x` string exists outside the generated JSON + history.

---

## 3. Remaining content fixes (mapped to files)

1. **Security hosted-lane tense** — `app/(en)/security/page.tsx:25` lede and
   `lib/data/security.ts:18-19` say the hosted lane *serves*; line 111 says
   *not yet live*. Rewrite 18-25 to future tense ("will serve / is designed
   to serve") until deployment; keep the known-limits item.
2. **Platform precision** — `lib/i18n.ts:47` "Linux & macOS one-liner" →
   Linux x86-64 install-gated; macOS/Windows binaries published but not yet
   install-gated (README §Install path). Align `components/renewal/
   InstallActions.tsx` download labels with the same wording.
3. **NLU claim** — `lib/i18n.ts:29` `heroRecall`: "no commands, no syntax" →
   "Ask normally in conversation. Your agent handles WhiteMagic through MCP
   behind the scenes." (dependable contract is still explicit routing).
4. **Dreaming first-claim** — `lib/i18n.ts:169`: remove/soften "We were the
   first to design the Dreaming system for AI".
5. **Emergent care** — `app/(en)/architecture/page.tsx:123`: drop "somatic
   hardware telemetry cultivate genuine emergent care"; keep the measurable
   mechanism.
6. **Frontier-labs convergence** — `lib/i18n.ts:192` `aboutP4`: soften to
   timestamped-paradigms + separately verifiable receipts, without asserting
   convergence.
7. **About measurement sentence** — `app/(en)/about/page.tsx:46`: "Where a
   claim can't be measured, we don't print it" → "Where a technical claim can
   be measured, we publish the measurement."
8. **PRAY vs PRAT** — canonical name is **PRAY** (WMv9 source: "Polymorphic
   Resonant Adaptive"). Fix enterprise lines 22/98 ("PRAT" → "PRAY") and any
   other live PRAT uses.
9. **R&D portfolio restructure** — `app/(en)/rd/page.tsx`: reorganize the
   thermometer + spinoff catalog into **SHIPPED** (WhiteMagic) / **ACTIVE
   RESEARCH** (MandalaOS, VIOLET, SutraCode) / **INCUBATED PROJECTS** (linked
   project cards) / **LONG-HORIZON RESEARCH** (energy/ecology/civic). Keep
   the material; change the reading: a lab portfolio, not one company.
10. **Enterprise licensing** — if any "Enterprise Sovereign License" language
    survives in the deployed page, reframe as **Enterprise Assurance &
    Support** (warranty/indemnification, deployment help, advisory, hardened
    configs, SLAs) — MIT already permits commercial embedding.

---

## 4. Verification and freeze

```bash
cd ~/Desktop/WHITEMAGIC/whitemagic-site
npm run check-facts      # drift gate (after the new sync lands)
npm run typecheck
npm run build
# then deploy and re-check the live pages for: version, date, platform,
# dream phases, security tense, PRAY
```

**Acceptance for the pass:** every review item above either fixed in-tree or
explicitly explained; facts generated from the manifest; a redeploy; then
freeze the homepage structure and watch install/activation rather than
rewriting copy.

**Guardrails:** another session has uncommitted work in `whitemagic-site`
(`docs/hetzner/*`, `staged/routes-app-grants/page.tsx`) — stage only touched
files, never `git add -A`. The canonical site repo is `whitemagic-site`
(`master`); `whitemagic-site-renewal` is historical.

---

## 5. Truth-and-consistency pass — close-out (2026-09-14)

### Done

- **Authority chain (site):** `scripts/sync_release_facts.py` + `npm run
  sync-facts|check-facts`. The signed manifest is snapshotted to
  `public/api/release-manifest.json`; `lib/generated/release.json` drives
  `lib/facts.ts` (version, release date, crates, tests when present) and
  `installReceipts` (date). `--check` fails on drift and scans for hardcoded
  `9.x.y` literals outside an allowlist. Site commit `bda815d`.
- **Authority chain (WMv9):** `release_manifest.py` now emits per-target
  `size` + `install_gated`, `crates`, optional `tests`/`benchmarks`,
  `supported_profile` (additive, schema-1). Commit `95be6dc`, rides v9.1.5;
  until then the generator reports `note: manifest predates the extended
  facts schema` and the site falls back to documented constants.
- **Content fixes (all review items):** heroRecall rephrased; 98% calibrated
  + methodology link + `/prove-it` methodology block; hosted lane future
  tense (EN+ZH); install hint + jsonld platform precision; Dreaming
  first-claim removed; "genuine emergent care" removed; About measurement
  sentence softened; frontier-labs paragraph softened; PRAT → PRAY;
  capability manifest + routes now 9 discrete entrypoints.
- **R&D restructured** (EN+ZH): SHIPPED / ACTIVE RESEARCH / INCUBATED
  PROJECTS / LONG-HORIZON RESEARCH.
- **Verified:** `check-facts` ✅, `check-data` (all four steps) ✅,
  `typecheck` ✅, `build` 62/62 pages ✅.

### Remaining

1. ~~Push `bda815d` and redeploy~~ **DONE — pushed to `master`, Vercel
   redeployed, live-verified 2026-09-14:** homepage shows v9.1.4 + the
   rephrased hero + methodology link; `/security` future tense; `/rd`
   portfolio title; `/enterprise` PRAY only; architecture 12-phase with no
   "emergent care"; about measurement sentence live; install-gate hint live.
2. **WMv9 push is held** — `95be6dc` sits on main behind the concurrent
   session's 7 unpushed commits; push when they do (or cherry-pick later).
3. Follow-up wiring: `release.yml` should pass `--tests-json` /
   `--benchmarks-file` into the manifest build so the site's generated facts
   carry test + benchmark snapshots without fallbacks.
4. WMv9 README/llms.txt: consume the manifest fields at release time (the
   WMv9 side still prints a few version strings, now guarded by
   `version_truth.py`).
5. After deploy: **freeze the homepage structure** and measure
   install/activation rather than rewriting copy.

---

## 6. Meantime workstream — reviewer's four questions (2026-09-14 late)

While the parallel sessions finished, we worked the reviewer's four
practical questions instead of adding capability.

### A — Do all public surfaces agree? (checker built, 33/33 green)

`whitemagic-site/scripts/check_public_surfaces.py` (commit `3b64349`):
- offline mode checks the capability manifest, release-manifest snapshot,
  `llms.txt` / `llms-full.txt` against the generated release facts;
- `--live` additionally checks the deployed `/api/manifest(.json)`,
  llms surfaces, MCP server card (both paths), agent card, **homepage**
  version marker, npm, Docker Hub, and the MCP registry;
- exit 1 on drift; unreachable warns unless `--strict`.
- `npm run check-surfaces` / `check-surfaces:live`.
- Live run: **all 33 checks green — one story everywhere.**

### B — Can a new AI onboard without hand-holding? (two doc gaps fixed)

Clean-roomed the agent path (`skill.md` → vocabulary → MCP calls) with a
scratch store:
- `session.record` / `session.checkpoint` require `session.start`, which the
  vocabulary table omitted → added the row plus an explicit prerequisite
  note; `memory.update` galaxy caveat documented.
- `wm grimoire` is real (7 steps, `--json`, `--write` patches client configs
  with comments preserved) but **ships after v9.1.4**; the parallel session
  reworded `skill.md` to be version-agnostic (`commit e436f2d`) before we
  finished — no further action.
- The site's `llms.txt` / `llms-full.txt` already document `session.start`
  correctly, so only `skill.md` needed the fix.

### C — First continuity inside a minute? (yes: ~3 s install → verified)

Measured on this host with a fresh `HOME`:
- `install.sh` (real v9.1.4 download) → 2.41 s; `wm --version` → 6 ms;
  `wm selftest` → 556 ms → **install → verified 2.97 s**.
- `wm grimoire` full run (host + substrate + release + memory + continuity
  demo) → **3.15 s total**, `ready: true`.
- Scratch serve ready in 592 ms; `session.start` 149 ms → `memory.create`
  142 ms → `session.record` 21 ms → `session.checkpoint` 26 ms →
  `session.continuity` returns the turn → **~0.65 s**.
- Machine-time from nothing installed to first successful continuity: **~7 s**.
  The remaining time is human reading/restarting the client, not tooling.

### D — Small under-the-hood fixes

1. **`wm doctor` partial-Landlock is INFO, not WARN** — verified in a clean
   worktree (compile + clippy clean), but **parked as a patch** because the
   parallel session was mid-flight in `wm.rs` (`wm connect`):
   `MANDALA_OS/patches/d1-doctor-partial-info.patch` — apply after their
   commit lands (`git apply` then test).
2. **Release facts wired end-to-end** (WMv9 `3d41f45`): `ci.yml` tees the
   Linux test run and uploads `tests-summary`; `release.yml` best-effort
   fetches that artifact (and `benchmark-results`) for the tagged commit and
   passes `--tests-json` / `--benchmarks-file` into `release_manifest.py`.
   Absent artifacts omit the fields — no fabricated numbers.
3. **Dashboard retention line** (lakshmi `01b1a74`): `/api/retention` wraps
   `telemetry.retention`; the Policies panel shows prune-due/next-eligible.
   Verified live: on the 9.1.4 fleet it returns `available: false`
   (Unknown tool) and the line hides; 11 dashboard tests green.

### Push state after this workstream

- `whitemagic-site`: `3b64349` local (push = deploy).
- `whitemagic`: `3d41f45` local; pushes stay held until the parallel session
  pushes its own commits (D1 patch applies after that).
- `lakshmi`: `01b1a74` local.

---

## 7. Reviewer's v9.1.4 clean-room follow-up (2026-09-14 late)

A second clean v9.1.4 pass (checksum-verified, empty HOME) confirmed the
release fixed the first run's failures: restart continuity, empty-newest-
session skip, importance fidelity, tags-only `memory.query`, `memory.find`
alias, supersession/replay byte-exactness, `wm setup` preservation, backup/
restore, ingestion idempotence + `.env` exclusion, the MCP init rhythm and
the three-strikes retry-loop warning. New items, triaged:

**Already fixed on main since v9.1.4** (they tested the tag):
- `wm status` fresh-install message — now "No working store yet" with the
  verify (`quickstart`) vs initialize (`serve`) split.
- `wm selftest` quiet by default (`--verbose` opts into diagnostics; the
  error-level filter landed post-9.1.4).
- NLU misroutes — `recall X`, `find X`, "what do you remember about",
  "what did we decide about" now route to `memory.search` (`0f06d73`, tests
  included).
- README surface wording — already "the `wm` meta-tool plus a …".

**Fixed by this workstream:**
- **Auto-logged friction → Telemetry** (`whitemagic 20aec8c`): the dispatch
  auto-logger (errors/anomalies/regressions) writes and dedups in Telemetry
  instead of Codex; `friction_hash_exists` checks both homes; manual
  `friction.log` stays Codex; `friction.review` + the autonomous
  Improve/Redteam/Research cycles read both. wm-tools 835 + wm-cognitive 714
  tests green; clippy clean.
- **Grimoire teach step (six primitives)** — the parallel session is
  actively rewriting `grimoire.rs` (embedder probing, first-run polish), so
  the six-primitive teach/test idea should be coordinated there rather than
  duplicated. It is the reviewer's main "next leap" recommendation.
- **Docs exactness** — the site's surfaces checker already enforces the
  9-entrypoint wording; README was already exact.

---

## 8. Pre-ceremony close-out (2026-09-14, after all parallel sessions)

**Parked items settled:**
- D1 doctor patch applied at the merged tip (`b4538ae`): Landlock `partial`
  is INFO; failed/unsupported stays WARN. The parked patch file can be
  deleted.
- `rsi.rs` formatting committed (`8a9e6ff`) — tree is clean.
- `release.sh 9.1.5 --dry-run` completes end-to-end at the tip: version
  truth 14/15 surfaces carry references and all agree on 9.1.4
  (`SECURITY.md` now has zero version literals by design).

**Grimoire review (finished implementation):**
- 620 lines, 7 steps (host → substrate → release → agent → memory → teach →
  continuity); read-only unless `--write`; `--write` delegates to the same
  `setup::connect_with` as `wm connect` (one wiring path); continuity proves
  close/reopen recovery on a throwaway store; `probe_embedder` does a real
  500 ms TCP check and reports configured-but-unreachable honestly; release
  check skips offline. Live run at the tip: **all 7 steps OK in 2.05 s**,
  client wired with backup, comments preserved.
- Teach surfaces are contract-tested (`teach_surfaces_agree_on_the_vocabulary`
  — grimoire VOCABULARY ↔ skill.md ↔ MCP instructions); it already caught
  `session.start` drift once.
- Nits for v9.1.6, not blockers: `host_step` reports macOS/Windows as OK
  although only Linux x86-64 is install-gated (could distinguish "published,
  not gated"); the teach step teaches but does not quiz the agent; the
  embedder probe uses the first resolved address (IPv6-first could
  false-negative a v4-bound endpoint).

**Ceremony state:** WMv9 clean, 40+ commits ahead of origin, CI flake retries
(`62e75ef`) will be exercised by the launch push; signed tags are registered
and proven Verified; site is deployed with the truth pass + surfaces checker.

---

## 9. v9.1.5 ceremony close-out (2026-09-14, ~04:45 UTC)

**Shipped.** Tag `v9.1.5` (signed) on `52fb0b7`; Release workflow completed
all channels; `release-health.json` on the release reports **healthy** with
**npm + Docker install certifications passing 8/8 selftest checks each**.

| Surface | Result |
|---|---|
| GitHub Release | live — 32 assets (12 required) |
| crates.io | 15/15 crates at 9.1.5 |
| npm | `whitemagic-mcp@9.1.5` live |
| Docker Hub | `lbailey94/whitemagic:9.1.5` live |
| MCP registry | `io.github.lbailey94/whitemagic-mcp@9.1.5` live |

### The one incident (and the fix)

`release.sh` aborted at its own CI gate, but by then the tag was pushed and
the tag-triggered Release workflow auto-published. Root cause of the red CI
was **Windows-only `-D warnings` compile failure in test code**:
`crates/wm-memory/src/episodic.rs` imported `chrono::{DateTime, Utc}` and
`uuid::Uuid` for Q06 helpers that are all `#[cfg(unix)]`. Fixed forward on
main (`19f1932`); the rerun is green through Linux/macOS and the Windows job
is executing tests (no compile failure). Test/benchmark facts were therefore
absent from the 9.1.5 manifest (CI not green at manifest-build time) — the
site's generated facts note and fallbacks handled that.

**Release-eng follow-up:** `release.sh` pushes the tag before waiting for CI,
so a gate failure cannot prevent publication. Consider waiting for CI green
*before* `git push origin v$VERSION`, or having the script reconcile/announce
post-tag failures (the health workflow already reconciles registries).

### Manual tail (done)

- Site synced to v9.1.5 (`f98ae4e`, deployed): manifest snapshot + generated
  facts (sizes, install gating, 15 crates), llms surfaces, capability
  manifest. `check-facts`, `check-surfaces`, typecheck, build all green.
- Changelog heading finalized to `2026-09-14` (`b114756`).

### First live `wm update` (release-eng item 3) — PASS

`wm update install`: manifest signature verified (Ed25519) → musl 9.1.5
downloaded (24,726,752 bytes = manifest size) → sha256 verified → candidate
`wm selftest` pass → backup → atomic swap → post-swap selftest pass.
Deliberate `wm update rollback` → 9.1.4 verified, then re-install → 9.1.5
verified. `install.json`: version 9.1.5, previous 9.1.4.

**Note:** the fleet `wm-serve@*` units still hold the old 9.1.4 inode until
restarted (restart deliberately left to Lucas).

---

## 10. Trust double-check + homepage cadence band (2026-09-14 late)

**Verification (all clean):**
- Public-surface guard: clean.
- `gitleaks detect` over full history: **no leaks found** (469 commits,
  ~296 MB scanned).
- Release diff `v9.1.4..v9.1.5`: no `.env`/key/credential/private/dev paths.
- Release assets: binaries + sha256 + cosign bundles + SBOMs +
  manifest/signature + `release-health.json` + benchmarks only.
- Tag `v9.1.5`: GitHub-verified (`verified: true, reason: valid`).
- Live surfaces checker (`--live --strict`): one story everywhere at 9.1.5.
- `release_health.py --version 9.1.5`: HEALTHY, npm + Docker install
  certifications pass.

**Homepage:** new `#cadence` band (`whitemagic-site cee5b7c`, deployed):
"Shipped daily. Fixed fast when you tell us." — daily verified releases,
signed across all channels; constructive feedback typically ships as a fix
within 48 hours (often the same day); thanks to contributors/testers/
supporters with issues + release-history links. EN + ZH; /about cadence
copy aligned. Live-verified after deployment.

**Noted cadence context for future planning:** daily signed releases are
top-percentile velocity; the metric to watch is escaped-defect rate, and a
stable-pointer/nightly channel split is the pressure valve if churn ever
reads as instability.
