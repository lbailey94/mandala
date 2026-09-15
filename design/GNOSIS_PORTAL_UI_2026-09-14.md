# Gnosis Portal UI — aesthetics, ratios, UX & capability parity (v0.1)

**Status:** design proposal for review. No implementation commitment; Phase 0 is
host-side and reversible.

**Scope:** the visual + interaction language of the MandalaOS face — the living
Mandala (ambient), the panel status, the Gnosis window (deep view), Stoic
notifications, and the TTY fallback — plus the plan to reach desktop capability
parity with Zorin OS / Linux **without forking the desktop stack**.

**Lineage:**
- `design/---MandalaOS.txt` — Anti-Maya transparency, Reflection of State,
  Gnosis Portals, Koshas as layers, "observing the living Mandala itself"
- concept review 2025-05-26 — Tiferet (beauty via balance), Samma-Meter,
  Stoic cards, the pastel desktop mockup, ">40 % of vector surface area" rule
- `feasibility/harmony-vector-spec.md` — 7 dims, guna tagging, ladder
  (observe/notify/nudge/throttle/isolate), Tauri dashboard + Sankey
- `design/ACTUATION_HYSTERESIS_2026-09-13.md` — enter/exit bands, dwell,
  cooldown, decision records, "plain language, no Rego"
- `LAKSHMI/README.md` — today's surfaces (stdlib server :3109, mirror,
  `/api/*`, Samma-Meter, explain lines)

---

## 1. Thesis and design laws

The UI is the mirror, not the show. Beauty is what balance looks like when
rendered truthfully (Tiferet). Ten laws; every later decision cites one.

1. **One channel, one meaning.** Hue = identity. Saturation = honesty
   (epistemic quality). Lightness = position vs the sufficiency band. Opacity =
   freshness. Glow = breach. Texture = guna. Thickness = accumulation. Gaps =
   blockage.
2. **No silent zeros.** Unavailable is a hatched gap, never an empty bar.
3. **Hue never encodes quantity or quality.** Energy is always the same hue
   whether it is 0.1 or 1.0.
4. **The mirror gets pale when it doesn't know.** Proxy and stub readings are
   desaturated; measured readings are vivid (RAPL vs PSI vs cold start).
5. **Fade is time.** Data ghosts as it ages; a stalled sampler stops breathing
   and drains (Anti-Maya).
6. **Glow is scarce.** Only `confirmed` policy state glows; at most one ring
   glows at a time, or none do (global-breaker aesthetic).
7. **Motion is event or heartbeat, never decoration.** Three legal motions:
   heartbeat (window emitted), transition pulse, flow (data actually moving).
8. **Every mark is a portal.** Any visual answers "why?" in ≤ 3 clicks
   (explain → source → evidence record).
9. **Plain language first, Sanskrit second.** "Responsiveness low" before
   "rajasic"; the metaphor is a gloss, never a requirement.
10. **The mirror discloses its own cost.** The renderer's own CPU/energy is a
    token in the vector; it turns itself amber before it becomes Maya.

---

## 2. Capability parity with Zorin OS / Linux

**Strategy: inherit, don't fork.** MandalaOS ships *on* NixOS + GNOME
(Mutter/Wayland, Zorin is GNOME-based). The Mandala layer is an extension + a
lens app + system services; stock behavior stays one toggle away ("Plain
mode"). This is how a small team has a desktop whose capability equals
Zorin/Linux in window management, networking, audio, printing, accessibility,
updates, and multi-monitor — while the differentiation lives in telemetry,
governance, and memory.

| Capability | Owner | Mandala hook |
|---|---|---|
| Compositor, windows, workspaces | GNOME/Mutter | none (never fork) |
| Launcher, dock, overview, search | GNOME shell | "Mandala" + "Explain last decision" entries |
| Settings | GNOME Settings | add **Mandala** panel: telemetry, policy, consent, theme |
| Files | Nautilus | provenance/openness columns via Gnosis portals (P3) |
| Notifications | GNOME | Stoic card style + policy inbox (see §7) |
| Updates / release | NixOS + WM release machinery | custody gate, release-health surfaced calmly |
| Network, power, audio, display, a11y | GNOME/NixOS | dims 2/4/5 show their real cost on the Mandala |
| Terminal | stock + `wm` | TTY mandala for headless/boot |
| Packaging/distro | NixOS flake | Sovereign Edition; public ISO stays gated |

**Explicit non-goals:** custom compositor, microkernel, kernel work, package
manager reinvention. Those are gated research (PLATFORM_DIRECTION), not the
path to a usable desktop.

**Plain mode:** one switch (Zorin-like "layouts" spirit) that hides the
Mandala surfaces and leaves a clean GNOME session. Intuitiveness must not
depend on liking the metaphor.

---

## 3. Surfaces

| # | Surface | Where | Interaction | Refresh |
|---|---|---|---|---|
| 1 | **Living Mandala** (ambient) | desktop/wallpaper widget, lock screen (compact) | hover = labels; click = Gnosis window | 10–30 s, on-change only |
| 2 | **Panel glyph** (status) | GNOME top bar via extension | click = popover: 7 rows + worst-state | 5 s |
| 3 | **Gnosis window** (lens) | GTK4 app (P1) / web `/mandala` (P0) | full drill-down, history, flows, portals | 2–30 s |
| 4 | **Stoic cards** | notification area + inbox | ack/dismiss (logged), action links | event |
| 5 | **TTY mandala** | console/headless VM, `lakshmi.py` render | static Unicode, 80×24 safe | 1 window |
| 6 | **Host dashboard** (dev) | `:3109`, `chrome --app=…` | tuning harness; same grammar | 2 s |
| 7 | **Window-title accent** (P1/P2) | titlebar of every window (compositor-side) | ambient, no interaction; opt-in | on state change |

Surface 7 (owner idea, 2026-09-14): the titlebar carries a thin state accent so
every window is a small mirror of the machine's ecological homeostatic state —
calm = neutral hairline (or none), holding = amber underline, breach = red
underline. Rules: never recolor text, never flash, accent width ≤ 2 px (scales
with HiDPI), title readability always wins, and a window whose own process is
implicated may carry a stronger accent than the global state (P3). It must be
possible to turn off in one place (Mandala settings) and to switch the whole
accent set to monochrome. Implementation: a GNOME extension drawing the
underline via window decorations is not available on stock GNOME — realistic
paths are a GNOME-compositor effect (Mutter) or an app-level convention in
Sovereign's default apps; treat as P1 research, not a promise.

Layout sketch (Gnosis window, 1280×800 min):

```
┌──────────────────────────────────────────────────────────────┐
│  ◉ harmony 0.61   heartbeat · 12s ago        [plain] [theme] │  header 56
├───────────────┬──────────────────────────────────────────────┤
│               │  Waves (bands · cues)                        │
│   MANDALA     │  ── fairness ─ responsiveness ─ throughput …  │
│   (rings)     │                                              │
│   320 px      │  Policies (step 0 · observe)                 │
│               │  ▸ responsiveness  ◐ band 0.42  [explain]    │
│               │  ▸ bridge trio      ● clear                  │
│               ├──────────────────────────────────────────────┤
│  [portals]    │  Flows (Sankey: prana/energy/net)  P3        │
│               ├──────────────────────────────────────────────┤
│               │  Stoic inbox / decision records              │
└───────────────┴──────────────────────────────────────────────┘
```

---

## 4. Encoding grammar (state → channel)

| Channel | Meaning | Values |
|---|---|---|
| Hue | identity, fixed | one hue per dim; guna hues for textures; never state |
| Chroma (saturation) | epistemic quality | measured 0.75 · proxy 0.45 · stub/neutral 0.25 · unknown 0.0 |
| Lightness | position vs sufficiency band | band shaded between enter/exit radii; deviation darkens/lightens, not reddens |
| Opacity | freshness | fresh 1.0 · aging 0.75 · stale 0.45 · lost 0.25 + hatch |
| Glow | breach only | confirmed state; r = 0.08R; one ring max |
| Pulse | event / heartbeat | 1 pulse per transition; 1 heartbeat per emitted window |
| Texture | guna | sattvic smooth · rajasic granular · tamasic frosted |
| Thickness | accumulation | karma debt thickens its arc; 0–2 px at v0 scale |
| Gap/hatch | blockage / unknown | dharma blocked = knot in flow; unknown = diagonal hatch |
| Position | deviation | radial distance inside/outside the band, same scale for all 7 dims |

**Samma-Meter contract:** enter-side = hatched warm; band = neutral shaded;
clear = solid cool; **under-use = hollow ghost** (not green). The 40 % rule
(concept review) is re-read as: highlight the worst dim when its share of
total normalized deviation exceeds 40 % — at most one highlight at a time.

---

## 5. Ratios, geometry, motion

**Grid & type**
- Base unit 4 px; spacing 4/8/12/16/24/32/48/64; panel radius 10; cell 8.
- Type 11/12/14/16/22/34/42 px, line-height 1.45; max 3 sizes per card.
- Body text ≥ 12 px; glance labels ≥ 11 px; numeric readouts tabular.

**Mandala geometry**
- Diameters: desktop 320 · panel popover 220 · ambient compact 160.
- Bindu (center) r = 0.12 R; 7 rings occupy 0.20 R → 0.95 R; ring band
  width = 0.107 R; inter-ring gap = 0.02 R; 2 px notch at 12 o'clock as
  origin; labels at 45° with leader lines ≥ 2 px.
- One scale for all dims (0–1 normalized); never normalize per-ring.

**Ladders**
- Opacity: 1.00 / 0.75 / 0.45 / 0.25 + hatch (fresh → lost).
- Chroma: 0.75 / 0.45 / 0.25 / 0 (measured/proxy/stub/unknown).
- Glow: single pulse 500 ms on transition, then steady 0.35 opacity.

**Motion tokens** (cubic-bezier 0.2, 0, 0, 1)
- hover 120 ms · state change 240 ms · heartbeat 400 ms (4 % lightness
  swell) · view transition 800 ms max.
- `prefers-reduced-motion`: heartbeat and pulses become 1-frame lightness
  changes; no other motion exists to disable.

**Cadences**
- fast lane 2 s · panel 5 s · ambient 10–30 s on change · history 30 s ·
  rollups 60 s · health 15 s. Rendering cost scales down as surface size
  goes up (wallpaper is the cheapest surface, not the most expensive).

**Ambient/wallpaper budget (resolved 2026-09-14).** The wallpaper is the
cheapest surface, not the prettiest one: ≤ 0.3 % CPU average, ≤ 30 MB RSS,
30 s cadence, render-on-change only, no continuous animation, no glows or
shaders, and **pause all work when the surface is hidden or fully obscured**
(Page Visibility / Mutter occlusion on GNOME). A stale mirror stops the
heartbeat and drains opacity — the wallpaper itself must never be the reason
the vector moves. The P0 web page is a tuning harness and is exempt from the
RSS/CPU numbers (browser overhead); the shipping ambient renderer is the
GNOME extension (GJS) or a GTK4 widget, measured against this budget before
it is allowed near the desktop.

**Density & targets**
- Glance layer ≤ 7 elements (the dims); detail lists ≤ 5 rows before scroll;
  hit targets ≥ 44 px (touch) / 24 px (mouse); 4.5:1 text, 3:1 non-text.

---

## 6. Color system

Two themes, one semantic token set (never raw hex at call sites).

| Token | Calm (light) | Deep Slate (dark) | Use |
|---|---|---|---|
| ground | #F4F1EA paper | #12141A | background |
| panel | #FFFFFF | #1A1D26 | cards |
| ink / dim | #2C3E50 / #7A8699 | #E8EAF0 / #8B91A5 | text |
| clear | #5FD38A | #5FD38A | recovered (with solid texture + label) |
| band | #E8C15A | #E8C15A | holding (dashed outline) |
| enter | #E06060 | #E06060 | observing (hatched fill) |
| mint / lavender / peach / sky | #95E1D3 / #C9B6E4 / #F6C9A8 / #A8CFE8 | muted 60 % | dim identity hues (mockup lineage) |

Redundancy is mandatory: state is never color-only — position (inside/outside
band) + texture (solid/dashed/hatched) + label. High-contrast theme inherits
GNOME a11y settings; a monochrome mode exists for e-ink/TTY parity.

---

## 7. UX flows & intuitiveness tests

**Flows**
1. **Glance (3 s).** From any surface: is the system calm, holding, or
   breached? Answer = mandala silhouette (complete & calm / one ring dashed /
   one ring glowing) before reading a single word.
2. **Inspect (hover / focus).** One ring expands a one-line explain with the
   policy sentence already computed by `explain_policy()`.
3. **Drill (≤ 3 clicks).** ring → panel row → decision record (ts, value,
   enter/exit, dwell, evidence). Portal click = Gnosis.
4. **History.** Waves + rollups; cues mark threshold events, never invent
   history the store cannot show (gap appears as a gap).
5. **Failure (Stoic card).** Plain reason, what still works, next action,
   dismiss = acknowledge (logged). No red strobes, no dead ends.
6. **First run (Welcome Dojo, P1).** Three tasks: find today's harmony, explain
   one decision, switch to Plain mode. Completion means the UI is intuitive.
7. **Consent (P3, release-coupled).** Bicameral card: proposal, evidence,
   effect row, approve/deny; deny always carries the explain link (Gevurah/
   Chesed). Exists only when Yama steps > 0 ship.

**Tests (acceptance, not vibes)**
- 3-second read ≥ 4/5 people identify state correctly, unprompted.
- ≤ 3 clicks to any underlying record.
- Zero-training tasks pass for 4/5 new users (ties to the stranger-install
  gate ethos).
- Screenshot test: a static capture must be interpretable without the legend.
- Cost test: renderer < 1 % CPU, < 60 MB RSS, and visible in its own vector.

---

## 8. Observer effect & budgets

The GUI runs inside the system it measures. Rules:
- The lens process appears in fairness/energy like any other process; if its
  share > 1 %, its own glyph turns amber.
- Update on change, not on frames; ambient surfaces subscribe to the mirror
  file, not the store.
- Fail-soft: with WM down, everything still renders from the mirror, faded
  where data ages out (rule 5) — the dashboard already works this way.

---

## 9. Phases & acceptance

| Phase | Work | Acceptance |
|---|---|---|
| **P0 (done 2026-09-14)** | `/mandala` SVG in the existing dashboard, encoding harness against the live mirror; ambient mode + theme toggle | screenshot-verified vs live data; JS syntax clean; routes/state tests green |
| **P1** | one render core, two shells: GTK4 "Mandala Lens" + GNOME extension popover; Welcome Dojo; Plain mode; title-accent research | parity checklist §2 green inside GNOME 46; a11y pass |
| **P2** | VM integration: NixOS module, ambient widget, TTY mandala, observer budget | GUI cost visible in vector; matrix 13/13 stays green; gate screenshots |
| **P3** | depth: Nautilus/settings portals, consent cards, Sankey flows | every mark ≤ 3 clicks to a record; consume only post-gate |

**P0 calibration notes (implemented, 2026-09-14):** floors come from
`harmony-vector-spec.md` healthy ranges (fairness ≥ 0.50, responsiveness ≥ 0.30,
throughput ≥ 0.50, stability ≥ 0.80, energy ≥ 0.90, dharma/karma ≥ 0.50), not a
global 0.6 — a desktop's Gini-based fairness sits low by nature and the spec's
own healthy range is the honest reference. Zones are quiet context; the ring
in which the value currently sits is the emphasized one (Samma-Meter behavior).
Two known deltas: policy state in the fast lane can lag up to one emission
window behind the value; and auras only exist for dims with policies (the
other dims show value + floor, no band).

**Queued for next discussion (owner, 2026-09-14):** multi-monitor support
(sovereign VM on the TV over HDMI while the laptop drives its own display —
per-display mandala, focus/context rules, hot-plug), layout presets
(Zorin-like familiar modes), consent-card copy timing (with Yama steps ≥ 1),
and Sanskrit gloss policy (when a term is primary vs a tooltip gloss).

---

*Rule 10 applies to this document too: if a number here cannot be traced to
the mirror/API or a cited doc, it is budgeted as "to measure in P0", not
asserted.*
