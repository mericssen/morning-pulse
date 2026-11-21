"""Morning Pulse API.

GET  /api/checkup          run all checks + AI brief, store score
POST /api/fix/{check_id}   apply the whitelisted fix for a check from the last checkup
GET  /api/stats            minutes saved, streak, score history
POST /api/demo             {"enabled": true|false} toggle fault injection for the stage demo
"""
from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, checks, demo, fixes, store
from .models import score

app = FastAPI(title="Morning Pulse")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"],
                   allow_headers=["*"])

store.init()
_last: dict[str, checks.CheckResult] = {}


@app.get("/api/checkup")
def checkup():
    t0 = time.perf_counter()
    results = checks.run_all()
    check_s = time.perf_counter() - t0
    _last.clear()
    _last.update({r.id: r for r in results})

    s = score(results)
    store.save_checkup(s, [r.to_dict() for r in results])
    report = agent.brief(results)
    return {
        "score": s,
        "checks": [r.to_dict() for r in results],
        "brief": report,
        "timing": {"checks_s": round(check_s, 2), "total_s": round(time.perf_counter() - t0, 2)},
        "stats": store.stats(),
        "demo": demo.status(),
    }


@app.post("/api/fix/{check_id}")
def fix(check_id: str):
    r = _last.get(check_id)
    if r is None or not r.fix_id:
        raise HTTPException(404, "No fix available for this check - run a checkup first.")
    out = fixes.apply(r.fix_id, r.fix_args)
    store.save_fix(check_id, r.fix_id, out["ok"], r.minutes_per_week if out["ok"] else 0, out["message"])
    if out["ok"]:
        _last.pop(check_id, None)
    return {**out, "minutes_per_week": r.minutes_per_week if out["ok"] else 0, "stats": store.stats()}


@app.get("/api/stats")
def stats():
    return store.stats()


class DemoToggle(BaseModel):
    enabled: bool


@app.post("/api/demo")
def set_demo(body: DemoToggle):
    demo.enable() if body.enabled else demo.disable()
    return demo.status()


# Serve the built frontend (frontend/dist) when present, so one process runs everything.
_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
