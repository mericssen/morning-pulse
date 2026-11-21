"""The AI layer: turn raw check results into a short, prioritised morning brief.

Design choices:
- Claude only sees a compact JSON summary of the checks (no raw logs, no file names).
- Claude can only pick fix ids from the whitelist we pass in; the UI still asks the user.
- If no API credentials are configured, or the call fails, a rule-based brief is used,
  so the app always works offline / on stage.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from .models import CheckResult

MODEL = os.environ.get("MP_MODEL", "claude-opus-5-5")

SYSTEM = """You are Morning Pulse, a calm, friendly IT co-pilot that runs a 10-second check-up \
when an employee starts their workday.

You receive the results of device checks as JSON. Write the morning brief:
- headline: one short sentence (max ~12 words) on how the day looks for this device.
- actions: at most 3 items, most time-saving first, only for checks whose status is warn or crit. \
  Each message is one plain-language sentence a non-technical employee understands, saying what \
  is wrong and what the fix does. Use fix_id exactly as given for that check, or null if it has none.
- tip: one short, genuinely useful productivity tip related to today's state (or a positive note \
  if everything is fine). No generic filler.
Never invent checks, numbers, or fixes that are not in the input. No emojis."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "check_id": {"type": "string"},
                    "message": {"type": "string"},
                    "fix_id": {"type": ["string", "null"]},
                },
                "required": ["check_id", "message", "fix_id"],
                "additionalProperties": False,
            },
        },
        "tip": {"type": "string"},
    },
    "required": ["headline", "actions", "tip"],
    "additionalProperties": False,
}


def _compact(results: list[CheckResult]) -> list[dict]:
    return [{"check_id": r.id, "status": r.status, "detail": r.detail, "metric": r.metric,
             "fix_id": r.fix_id, "minutes_lost_per_week": r.minutes_per_week} for r in results]


def rule_based_brief(results: list[CheckResult]) -> dict:
    issues = sorted((r for r in results if r.status != "ok"),
                    key=lambda r: (r.status != "crit", -r.minutes_per_week))[:3]
    if not issues:
        headline = "All clear - your laptop is ready for the day."
    elif any(r.status == "crit" for r in issues):
        headline = f"{len(issues)} thing(s) will slow you down today - quick fixes below."
    else:
        headline = f"Mostly good. {len(issues)} small thing(s) worth fixing now."
    return {
        "headline": headline,
        "actions": [{"check_id": r.id, "message": r.detail, "fix_id": r.fix_id} for r in issues],
        "tip": "Fixing these now saves you about "
               f"{round(sum(r.minutes_per_week for r in issues))} minutes this week." if issues
               else "Good day to tackle your hardest task first - nothing on this device will get in the way.",
        "source": "rules",
    }


def _has_credentials() -> bool:
    return any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")) \
        or os.environ.get("MP_FORCE_LLM") == "1"


def brief(results: list[CheckResult]) -> dict:
    if os.environ.get("MP_NO_LLM") == "1" or not _has_credentials():
        return rule_based_brief(results)

    import anthropic

    payload = {
        "local_time": dt.datetime.now().strftime("%A %H:%M"),
        "checks": _compact(results),
    }
    try:
        client = anthropic.Anthropic(timeout=30.0, max_retries=1)
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason != "end_turn":
            return rule_based_brief(results)
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
    except (anthropic.APIStatusError, anthropic.APIConnectionError, StopIteration, json.JSONDecodeError):
        return rule_based_brief(results)

    # Guard: keep only actions that point at real checks / real fixes.
    known = {r.id: r for r in results}
    data["actions"] = [
        {**a, "fix_id": known[a["check_id"]].fix_id}
        for a in data["actions"]
        if a["check_id"] in known and known[a["check_id"]].status != "ok"
    ][:3]
    data["source"] = "claude"
    return data
