---
type: project_plan
title: "Project 001 — Unify the brain deployer (Current Orientation)"
description: The read-instead-of-a-handoff cold-start orientation for Project 001.
tags: [project-plan, orientation, deployer]
timestamp: 2026-07-21
status: draft
---

# Project 001 — Current Orientation

> Read this instead of a handoff to resume Project 001 cold. Short by design.

## What this project is
Fold Linux parity INTO the already-working `windows_deploy_brain.py` (branch inline only at OS-forced
steps), then rename that consolidated trunk to `deploy_brain.py` and retire `linux_deploy_brain.py`.
One shared build→deploy→verify spine (the Windows script's), with an `if _IS_LINUX` branch only at the
five OS-forced touchpoints. Full detail: `001_detail-unify_deploy_brain.md`. **Read NOTE 001-4 first.**

## The one thing to understand first
The Windows deployer already runs the correct process end-to-end; the Linux one diverged and broke
(gateway TLS cert never generated — a false-green from a bad `gen-cert.sh` call). So this is a **merge
into the Windows trunk**, not a rewrite and not a new file. **PIVOT (NOTE 001-4):** the earlier
clean-room `deploy_brain.py` + `PlatformBackend` ABC is REJECTED and discarded — we edit
`windows_deploy_brain.py` in place. Only five things are genuinely OS-forced (engine host+snapshot,
identity switch, seam mount, residency, firewall); everything else stays the Windows trunk untouched.

## Where the project stands
**PIVOT just landed (NOTE 001-4).** The prior "Sections 1 & 6 done" lived in a clean-room
`deploy_brain.py` that is now **discarded**; origin was reverted to baseline `30abc35` and the stray
Section-2 commit `13e8467` force-pushed away. What survives is knowledge, not code: the five OS-forced
touchpoints, the identity split (`sudo -u`/`run_as_brain --wsl`), and the no-false-green cert contract.
All plan docs are re-scoped to "extend the trunk". Design questions resolved: the Linux engine artifact
is `docker save` images + ollama-volume tar + config/cert bundle (NOTE 001-1). Nothing is BLOCKED.
Remaining code, all against `windows_deploy_brain.py`: Section 1 (platform switch + branch scaffolding),
2 (Linux path in `build_engine`), 3 (Linux snapshot/restore), 4 (Linux branches in `cmd_deploy`:
seam/gateway/residency/firewall), 5 (CLI parity), 6 (rc-checked cert on the Linux path), 7 (rename to
`deploy_brain.py` + retire `linux_deploy_brain.py` + delete rejected file + docs), 8 (rebuild dev_brain
via the unified path — clears the live outage, NOTE 001-3).
Recommended next: Section 1 (map the trunk's OS-forced touchpoints, add the switch) → 2/3 → 4.
Live `dev_brain` stays down by design until Section 8.

## What to read, in order
1. This file.
2. `001_status-unify_deploy_brain.md` — per-item status + `NOTE 001-K` decisions.
3. `001_detail-unify_deploy_brain.md` — the full plan, verbatim brief, traced code map.
4. `001_bugs_and_technical_debt-unify_deploy_brain.md` — BUG-001-1 (the cert false-green) + debt.

## Standing rules for keeping THIS project current (do these without being asked)
1. **Keep the status doc live** — update each item's status as work lands; add a `NOTE 001-K` for
   every decision (`grep "NOTE 001-"`).
2. **Archive verified sections** — move `VERIFIED` blocks into
   `001_status_archive-unify_deploy_brain.md`; leave a one-line stub.
3. **Keep this orientation current** — a couple of plain lines when the shape or next step changes.
4. **Log every meaningful action** — append ONE line to `001_action_log-unify_deploy_brain.md`.

The full lifecycle rules live in `PROJECT_PLAN_GUIDE.md` (same folder).

## Related tracking
- Bugs & tech debt: `001_bugs_and_technical_debt-unify_deploy_brain.md`.
- Sibling tool already cross-platform: `brain_doctor.py` (diagnose/repair) — consumes whatever this
  deployer produces; keep its probes in sync (DEBT-001-1).
