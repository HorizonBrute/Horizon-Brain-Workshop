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
Replace the two platform brain deployers (`windows_deploy_brain.py`, `linux_deploy_brain.py`) with a
single `deploy_brain.py`. One shared build→deploy→verify process; a thin `PlatformBackend` handles
only the OS-forced steps. Full detail: `001_detail-unify_deploy_brain.md`.

## The one thing to understand first
The Windows deployer already runs the correct process end-to-end; the Linux one diverged and broke
(gateway TLS cert never generated — a false-green from a bad `gen-cert.sh` call). So unification is
**subtraction toward the Windows process**, not a merge of two half-different flows. Only five things
are genuinely OS-forced (engine host+snapshot, identity switch, seam mount, residency, firewall);
everything else is shared. See NOTE 001-1 for the one real open design question.

## Where the project stands
Planning complete; **no product code written yet.** Two investigations done (root-cause of the cert
bug + full Windows build-engine lifecycle map) — both distilled into the detail doc. One decision
gates the build: **the Linux engine artifact** (NOTE 001-1) — recommendation is `docker save` +
config/cert bundle, awaiting user confirm (Section 3 BLOCKED on it). Section 6 (gen-cert hardening,
BUG-001-1) can land first, independent of the refactor. The live `dev_brain` is intentionally left
down until Section 8 rebuilds it via the unified path (NOTE 001-3).
Recommended build order: 1 → 6 → 3(confirm) → 2 → 4 → 5 → 7 → 8.

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
