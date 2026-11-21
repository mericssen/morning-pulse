# Morning Pulse

**LauzHack 2026 · Nexthink track: Digital Employee Experience**

A 10-second morning check-up for your work laptop. When you start your day, Morning Pulse:

1. runs fast, read-only checks: disk and temp junk, uptime, background CPU hogs, Teams/Outlook network latency and DNS, battery, pending update reboots, startup apps
2. asks Claude to turn the raw results into **one headline and at most 3 actions**, written in plain language
3. offers a **one-click fix** for each action, chosen from a whitelist and applied only after you approve it
4. tracks **minutes saved per week**, a daily streak and a 7-day score trend

**Why open it when nothing is broken?** Because it catches problems before they happen ("disk full in 6 days", "13 days without a restart"), shows the time you've won back, and takes 10 seconds.

## Run

```powershell
.\run.ps1            # builds the UI if needed, then serves everything at http://127.0.0.1:8000
```

Dev mode with hot reload:

```powershell
.\run.ps1 -Dev                      # API on :8000
cd frontend; npm run dev            # UI on :5173 (proxies /api)
```

**Open automatically at Windows sign-in** (current user, no admin needed):

```powershell
.\scripts\install-autostart.ps1     # adds a shortcut to the Startup folder
.\scripts\uninstall-autostart.ps1   # removes it and stops the background server
```

At sign-in the server starts hidden (logs go to `%LOCALAPPDATA%\MorningPulse`) and the card opens as an Edge app window.

**AI brief:** set `ANTHROPIC_API_KEY` (or log in with `ant auth login`). Without credentials the app uses a rule-based brief, so it still works offline and on stage.
Other env vars: `MP_MODEL` (default `claude-opus-5-5`), `MP_NO_LLM=1` (always use the rule-based brief), `MP_DB` (path to the SQLite file).

**Demo mode:** the "Demo" chip at the top right injects simulated faults (full disk, slow DNS, a CPU hog, 13 days of uptime), so there is always something to fix live. Fixes then clear those simulated faults; nothing on the machine is touched.

## Architecture

```
backend/app/
  checks.py   device checks (psutil + Windows registry), run in parallel, each one isolated
  fixes.py    whitelisted fixes: clean_temp, flush_dns, kill_process, schedule_restart
  agent.py    Claude call: compact JSON in, structured JSON out, rule-based fallback
  store.py    SQLite: checkups, fixes, minutes saved, streak
  demo.py     simulated fault injection
  main.py     FastAPI: /api/checkup, /api/fix/{id}, /api/stats, /api/demo; serves frontend/dist
frontend/     React + Vite, a single-screen morning card
```

Safety: the model never sees raw logs and never writes commands. It can only reference check ids and fix ids that come from our code, and every fix needs a click.

## Team split (3 people)

| Who | Owns |
|---|---|
| A | `checks.py` + `fixes.py`: more checks (boot time from Event Log 100, Teams cache size, Wi-Fi signal, mic/camera before the first meeting) |
| B | `agent.py` + `main.py` + `store.py`: prompt quality, meeting-aware brief, "Windows notification at login" (Task Scheduler) |
| C | `frontend/` + demo script + pitch: polish, animations, weekly summary view, slides |

## Roadmap ideas
- Calendar-aware prep: "First meeting at 09:30: mic, camera and network checked"
- Forecasts: "at this rate the disk is full in 6 days"
- IT cockpit: aggregate silent issues across devices, ranked by hours lost
