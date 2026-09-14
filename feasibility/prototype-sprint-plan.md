> **Reality check 2026-09-13:** Qubes-first setup superseded by the NixOS
> Sovereign VM; observability stack staged (Tetragon first, Falco/OPA
> later). See `CURRENT_REALITY_2026-09-13.md` §4 and the reality-adjusted
> section in `implementation/lakshmi-yama-sprint-plan.md`.

# MandalaOS: Prototype Sprint & Performance Strategy

## 🏃 Step-by-Step Prototype Plan (The "First Flow")

### Week 1: The Observability Root (Lakshmi & Yama)
1.  **Environment Set-up**: Install QubesOS (or a Qubes-on-Zorin VM) as the structural base.
2.  **eBPF Harness**: Create a simple Python script using `bcc` (BPF Compiler Collection) to monitor process lifecycles.
3.  **The Karma Ledger**: Write eBPF probes that log network and file access to a local SQLite database (The Ledger).

### Week 2: The Core Interface (Maya)
1.  **Astro/Next.js Scaffold**: Build the "Gnosis Portal" dashboard using Astro for speed.
2.  **Tauri Wrapper**: Wrap the dashboard in Tauri to create the primary "Shell" app.
3.  **Live Telemetry**: Connect the Tauri Shell to the eBPF harness so the dashboard pulses when the kernel acts.

### Week 3: Ethical Interception (The Inter-Gana Bridge)
1.  **Inter-VM Communication**: Use Qubes `qrexec` to allow the Dashboard VM to talk to a "Security VM."
2.  **Consent Dialogs**: Create a Tauri-based pop-up that appears when eBPF detects a "Non-Dharmic" action (e.g., a new process trying to phone home).
3.  **The Loop**: User clicks "Allow" -> eBPF probe is updated -> Process proceeds.

### Week 4: Integration & Test
1.  **Scenario**: Boot the system, open a "Rajasic" (high-energy) app like VS Code.
2.  **Observation**: Watch the Harmony Vector shift. Check if eBPF captures the "Karma debt" of the extra CPU usage.
3.  **Iteration**: Refine the UI based on how intrusive the alerts feel (balancing Gevurah/Severity and Chesed/Mercy).

---

## ⚖️ Resource Comparison: Zorin OS vs. Mandala Hybrid

| Feature | Zorin OS (Standard) | Mandala Hybrid Prototype |
| :--- | :--- | :--- |
| **Idle RAM Usage** | ~800MB - 1.5GB | ~6GB - 10GB |
| **Architecture** | Monolithic (Fast, but "blind") | Compartmentalized (Visible, but "heavy") |
| **CPU Overhead** | Minimal | Constant (due to Xen and eBPF polling) |
| **Security Type** | Conventional (Firewalls, AV) | Structural (Isolation + eBPF Conscience) |

> [!WARNING]
> **Performance Hit**: MandalaOS in this hybrid form will feel "heavy" compared to Zorin. Zorin is optimized for speed; Mandala is optimized for **Consciousness** (knowing what happens).

---

## ⚡ Performance Strategy: "Lazy Activation" (Atma-Prasada)

To keep the machine snappy, we must ensure processes only exist when they are being "observed" or used.

### 1. "On-Demand" VM Booting
Instead of starting all Gana VMs at boot, the **Lakshmi Monitor** (Tauri) acts as a gateway. When you click a "Work" wedge on the radial palette, the system triggers the `qvm-start` command for that specific Qubes VM.

### 2. Sidecar Throttling
For heavy Electron apps like VS Code or Obsidian:
- **Freeze on Inactive**: Use Linux `cgroups` or `SIGSTOP` to "freeze" any Electron window that hasn't been focused for 5 minutes.
- **Thaw on Hover**: Use the Tauri Shell to detect mouse proximity to the window's boundary, sending `SIGCONT` to "wake it up" just before the user clicks.

### 3. eBPF Filtering (The "Quiet Mind")
Don't monitor everything at once. Use "Selective Gnosis":
- Only monitor "Rajasic" (Network-heavy) processes in high-detail.
- Keep "Sattvic" (Local, trusted) processes on a low-fidelity profile to save CPU cycles.

### 4. Zero-UI Dashboards
Build the "Lakshmi" backend in **Rust** (the heart of Tauri) so that even when the graphical dashboard is closed, the ethical monitoring continues with negligible impact on RAM.
