"""Y1.0 — actuator router skeleton (notify only; no enforcement).

Contract: `MANDALA_OS/design/ACTUATOR_CONTRACT_2026-09-15.md` (subject
identity, record v2, router, `WM_ACTUATION=0`).

What this module does today: consumes step-0 transitions, enriches every
record to v2 (``subject``/``step``/``actuator``/``undo_token``/``expires_at``),
and emits ladder step 1 (notify) for *confirmed* transitions while armed.
Notify never blocks, throttles, or kills anything; steps 2–4 stay unbuilt by
design. The kill switch is read on every call (not cached), so
``WM_ACTUATION=0`` takes effect within one window.
"""

from __future__ import annotations

import os
from collections import deque

ARM_ENV = "WM_ACTUATION"

# Policies whose subject is a process/tool identity captured at source (Y1.1);
# until then their records keep ``subject=None`` and stay notify-only
# (contract §2 rule 1).
BRIDGE_POLICIES = frozenset(
    {"spawn.undeclared.v1", "sandbox.degraded.v1", "shadow.access.v1"}
)

# Highest ladder step the router may apply, per policy (contract §5). Notify
# is the only actuator in Y1.0; nudge/throttle need earned observation windows.
POLICY_MAX_STEP: dict[str, int] = {}
DEFAULT_MAX_STEP = 1

# Bound on the duplicate-suppression ring (oldest keys evicted first).
APPLIED_MAX = 512


def armed_from_env(env: dict | None = None) -> bool:
    """``WM_ACTUATION=0`` disarms; anything else is armed (firebreak doctrine)."""
    value = (env or os.environ).get(ARM_ENV, "1")
    return str(value).strip() != "0"


def resolve_subject(record: dict) -> str | None:
    """Stable subject handle (contract §2); ``None`` when not yet captured.

    Captured subjects (``tool:``/``proc:``/``dim:``) always win; dim policies
    fall back to ``dim:<metric>``; bridge policies without a captured subject
    stay notify-only.
    """
    subject = record.get("subject")
    if isinstance(subject, str) and subject:
        return subject
    if record.get("policy_id") in BRIDGE_POLICIES:
        return None
    metric = record.get("metric")
    return f"dim:{metric}" if metric else None


def annotate_policies(policies: list[dict], router: "Router") -> list[dict]:
    """Disclose the kill switch + capability on every policy row (§6)."""
    return [
        dict(
            policy,
            actuator_armed=router.armed,
            actuator_max_step=router.max_step(policy.get("policy_id", "")),
        )
        for policy in policies
    ]


def notify_payload(record: dict) -> dict:
    """Plain-language bus payload for one notify action (explain-first)."""
    value = record.get("value")
    enter = record.get("enter")
    metric = record.get("metric")
    if record.get("direction") == "below":
        reason = f"{metric} fell below its sufficiency floor ({value} < {enter})"
    else:
        reason = f"{metric} crossed its threshold ({value} > {enter})"
    return {
        "policy_id": record.get("policy_id"),
        "version": record.get("version"),
        "subject": record.get("subject"),
        "metric": metric,
        "value": value,
        "state": record.get("state"),
        "step": record.get("step"),
        "actuator": record.get("actuator"),
        "reason": reason,
        "evidence": record.get("evidence"),
    }


class Router:
    """Enrich transitions to record v2 and apply the ladder (notify only).

    Idempotent per transition key; ``route`` returns
    ``(enriched records, notifications to emit)`` and never mutates its input.
    """

    def __init__(self, armed: bool | None = None) -> None:
        self._armed_override = armed
        self._applied: set[tuple] = set()
        self._applied_order: deque[tuple] = deque()

    @property
    def armed(self) -> bool:
        """Live kill-switch state; the env is re-read on every access."""
        if self._armed_override is not None:
            return self._armed_override
        return armed_from_env()

    def max_step(self, policy_id: str) -> int:
        return POLICY_MAX_STEP.get(policy_id, DEFAULT_MAX_STEP)

    def _remember(self, key: tuple) -> None:
        self._applied.add(key)
        self._applied_order.append(key)
        while len(self._applied_order) > APPLIED_MAX:
            self._applied.discard(self._applied_order.popleft())

    def route(self, observations: list[dict]) -> tuple[list[dict], list[dict]]:
        records: list[dict] = []
        notifications: list[dict] = []
        armed = self.armed
        for record in observations:
            enriched = dict(record)
            enriched["subject"] = resolve_subject(record)
            enriched["step"] = 0
            enriched["actuator"] = "none"
            enriched["undo_token"] = None
            enriched["expires_at"] = None
            if armed and record.get("state") == "confirmed":
                step = min(1, self.max_step(record.get("policy_id", "")))
                key = (
                    str(record.get("ts", "")),
                    str(record.get("policy_id", "")),
                    str(record.get("state", "")),
                )
                if step > 0 and key not in self._applied:
                    self._remember(key)
                    enriched["step"] = step
                    enriched["actuator"] = "notify"
                    notifications.append(enriched)
            records.append(enriched)
        return records, notifications

    def applied_count(self) -> int:
        """Size of the duplicate-suppression ring (bounded by APPLIED_MAX)."""
        return len(self._applied)
